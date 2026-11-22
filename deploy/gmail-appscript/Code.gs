/**
 * LeadScan — đẩy thư Gmail MỚI sang hệ thống để AI lọc cơ hội và tạo phiếu nháp.
 * Hướng dẫn cài: deploy/gmail-appscript/README.md
 *
 * Script Properties cần đặt:
 *   WEBHOOK_URL     https://leadscan.net/api/webhooks/gmail
 *   WEBHOOK_SECRET  trùng LEADSCAN_GMAIL_WEBHOOK_SECRET trên máy chủ
 * Script tự tạo:
 *   START_TS        thời điểm chạy setup() — thư nhận TRƯỚC thời điểm này không bao giờ được gửi
 *   CURSOR_TS       thời điểm thư mới nhất đã gửi thành công
 */

var MAX_PER_RUN = 30;        // số thư tối đa mỗi lượt (lượt chạy ≤ 6 phút)
var MAX_BODY_CHARS = 60000;  // cắt thân thư quá dài
// Tệp đính kèm: gửi NỘI DUNG (base64) các loại máy chủ đọc được chữ; tệp khác / quá lớn chỉ gửi tên.
var MAX_FILES = 20;
var MAX_FILE_BYTES = 10 * 1024 * 1024;   // 1 tệp
var MAX_TOTAL_BYTES = 15 * 1024 * 1024;  // tổng 1 thư (base64 ≈ 20 MB, máy chủ nhận tối đa 24 MB)
var READABLE_EXT = /\.(pdf|docx|xlsx|xlsm|pptx|txt|csv|tsv|html?|eml)$/i;
var READABLE_TYPE = /^(application\/pdf|text\/(plain|csv|html)|message\/rfc822|application\/vnd\.openxmlformats-officedocument\.)/i;
// Chỉ Hộp thư đến; bỏ Quảng cáo / Mạng xã hội / Diễn đàn (Gmail đã tự phân loại). Thư rác & thùng rác không nằm trong inbox.
var QUERY = 'in:inbox -category:promotions -category:social -category:forums';

function props_() {
  return PropertiesService.getScriptProperties();
}

/** Chạy 1 lần sau khi đặt WEBHOOK_URL + WEBHOOK_SECRET: ghi mốc bắt đầu và tạo trigger 5 phút. */
function setup() {
  var p = props_();
  if (!p.getProperty('WEBHOOK_URL') || !p.getProperty('WEBHOOK_SECRET')) {
    throw new Error('Chưa đặt WEBHOOK_URL và WEBHOOK_SECRET trong Project Settings → Script Properties.');
  }
  if (!p.getProperty('START_TS')) {
    var now = String(Math.floor(Date.now() / 1000));
    p.setProperty('START_TS', now);
    p.setProperty('CURSOR_TS', now);
  }
  ScriptApp.getProjectTriggers().forEach(function (t) {
    if (t.getHandlerFunction() === 'pushNewEmails') ScriptApp.deleteTrigger(t);
  });
  ScriptApp.newTrigger('pushNewEmails').timeBased().everyMinutes(5).create();
  Logger.log('Đã cài. Chỉ gửi thư nhận sau ' + new Date(Number(p.getProperty('START_TS')) * 1000) + ', 5 phút / lần.');
}

/** Dừng gửi thư (xoá trigger). Chạy lại setup() để bật lại — không gửi bù thư cũ trước mốc START_TS. */
function stop() {
  ScriptApp.getProjectTriggers().forEach(function (t) {
    if (t.getHandlerFunction() === 'pushNewEmails') ScriptApp.deleteTrigger(t);
  });
  Logger.log('Đã dừng.');
}

/** Kiểm tra URL + khoá: gửi gói rỗng có chữ ký, máy chủ trả 422 (thiếu trường) nghĩa là chữ ký đúng. */
function kiemTraKetNoi() {
  var res = post_('{}');
  var code = res.getResponseCode();
  if (code === 422) Logger.log('Kết nối OK: máy chủ nhận chữ ký.');
  else if (code === 401) Logger.log('Sai WEBHOOK_SECRET (hoặc đồng hồ lệch). Phản hồi: ' + res.getContentText());
  else if (code === 404) Logger.log('Webhook chưa bật trên máy chủ (LEADSCAN_GMAIL_WEBHOOK_SECRET trống) hoặc sai WEBHOOK_URL.');
  else Logger.log('Lỗi ' + code + ': ' + res.getContentText());
}

/** Trigger 5 phút: gửi thư mới (cũ → mới), dừng ở thư đầu tiên gửi lỗi để lượt sau gửi lại. */
function pushNewEmails() {
  var lock = LockService.getScriptLock();
  if (!lock.tryLock(1000)) return; // lượt trước chưa xong
  try {
    run_();
  } finally {
    lock.releaseLock();
  }
}

function run_() {
  var p = props_();
  var start = Number(p.getProperty('START_TS'));
  if (!start) throw new Error('Chưa chạy setup().');
  var cursor = Math.max(start, Number(p.getProperty('CURSOR_TS') || start));
  var me = (Session.getEffectiveUser().getEmail() || '').toLowerCase();

  var items = [];
  GmailApp.search(QUERY + ' after:' + (cursor - 60), 0, 100).forEach(function (thread) {
    thread.getMessages().forEach(function (m) {
      var ts = Math.floor(m.getDate().getTime() / 1000);
      if (ts > cursor) items.push({ m: m, ts: ts, thread: thread.getId() });
    });
  });
  items.sort(function (a, b) { return a.ts - b.ts; });

  var sent = 0;
  for (var i = 0; i < items.length && sent < MAX_PER_RUN; i++) {
    var it = items[i];
    var m = it.m;
    if (m.isInTrash() || (me && m.getFrom().toLowerCase().indexOf(me) !== -1)) { // thư chính mình gửi / đã xoá
      cursor = it.ts;
      continue;
    }
    var payload = JSON.stringify({
      id: m.getId(),
      thread_id: it.thread,
      from: m.getFrom(),
      to: m.getTo(),
      subject: m.getSubject(),
      date: m.getDate().toISOString(),
      body: (m.getPlainBody() || '').slice(0, MAX_BODY_CHARS),
      attachments: attachments_(m),
    });
    var code;
    try {
      code = post_(payload).getResponseCode();
      if (code === 413) { // quá lớn: gửi lại chỉ kèm tên tệp để không mất thư
        var lite = JSON.parse(payload);
        lite.attachments.forEach(function (a) { if (a.data) { delete a.data; a.skipped = 'too_large'; } });
        code = post_(JSON.stringify(lite)).getResponseCode();
      }
    } catch (err) { // mạng lỗi / quá thời gian chờ: lượt sau gửi lại (máy chủ chống trùng theo mã thư)
      Logger.log('Gửi lỗi (' + err + ') — lượt sau thử lại từ thư ' + m.getId());
      break;
    }
    if (code === 200 || code === 201) {
      sent++;
    } else if (code === 413 || code === 422) {
      Logger.log('Bỏ qua thư ' + m.getId() + ' (' + code + ')'); // thư quá lớn / thiếu người gửi: gửi lại cũng lỗi
    } else {
      Logger.log('Gửi lỗi ' + code + ' — lượt sau thử lại từ thư ' + m.getId());
      break;
    }
    cursor = it.ts;
  }
  p.setProperty('CURSOR_TS', String(cursor));
  if (sent) Logger.log('Đã gửi ' + sent + ' thư.');
}

/** Tệp đính kèm (không gồm ảnh chèn trong thân thư): tên, loại, dung lượng + nội dung base64 nếu máy chủ đọc được. */
function attachments_(m) {
  var total = 0;
  return m.getAttachments({ includeInlineImages: false }).slice(0, MAX_FILES).map(function (a) {
    var name = a.getName() || 'tep-dinh-kem';
    var type = a.getContentType() || '';
    var size = a.getSize();
    var item = { name: name, type: type, size: size };
    if (!READABLE_EXT.test(name) && !READABLE_TYPE.test(type)) return item; // ảnh, .doc/.xls cũ, .zip… → chỉ tên
    if (size > MAX_FILE_BYTES || total + size > MAX_TOTAL_BYTES) {
      item.skipped = 'too_large';
      return item;
    }
    total += size;
    item.data = Utilities.base64Encode(a.getBytes());
    return item;
  });
}

function post_(body) {
  var p = props_();
  var ts = String(Math.floor(Date.now() / 1000));
  var raw = Utilities.computeHmacSha256Signature(ts + '.' + body, p.getProperty('WEBHOOK_SECRET'), Utilities.Charset.UTF_8);
  var sig = raw.map(function (b) { return ('0' + (b & 0xff).toString(16)).slice(-2); }).join('');
  return UrlFetchApp.fetch(p.getProperty('WEBHOOK_URL'), {
    method: 'post',
    contentType: 'application/json; charset=utf-8',
    payload: body,
    headers: { 'X-LeadScan-Timestamp': ts, 'X-LeadScan-Signature': sig },
    muteHttpExceptions: true,
  });
}
