export type Role = "admin" | "staff";

export interface User {
  id: number;
  email: string;
  full_name: string;
  role: Role;
  is_active: boolean;
  created_at: string;
  last_login_at: string | null;
}

export interface UserRef {
  id: number;
  full_name: string;
}

export interface Contact {
  id: number;
  full_name: string;
  position: string;
  email: string;
  phone: string;
  is_primary: boolean;
}

export interface Profile {
  offering: string;
  target_customers: string;
  target_regions: string[];
  opp_types: string[];
  expected_tickets: string;
  notes: string;
  updated_at: string;
}

export interface Activity {
  id: number;
  kind: "created" | "status" | "note" | "update" | "assign";
  content: string;
  created_at: string;
  actor: UserRef | null;
}

export interface CompanyListItem {
  id: number;
  code: string;
  status: string;
  name: string;
  tax_code: string;
  industry: string;
  province: string;
  created_at: string;
  assigned_to: UserRef | null;
  primary_contact: Contact | null;
}

export interface Company {
  id: number;
  code: string;
  status: string;
  name: string;
  tax_code: string;
  industry: string;
  company_size: string;
  province: string;
  address: string;
  website: string;
  source: string;
  ip: string;
  created_at: string;
  updated_at: string;
  assigned_to: UserRef | null;
  contacts: Contact[];
  profile: Profile | null;
  activities: Activity[];
}

export interface Page<T> {
  total: number;
  page: number;
  page_size: number;
  items: T[];
}

export interface Meta {
  statuses: Record<string, string>;
  roles: Record<Role, string>;
  sizes: string[];
  regions: string[];
  opp_types: string[];
  tickets: string[];
  staff: UserRef[];
}

export interface Stats {
  total: number;
  by_status: Record<string, number>;
  new_today: number;
  new_7d: number;
  daily: { date: string; count: number }[];
  recent: CompanyListItem[];
}
