export type EmployeeDocument = {
  readonly id: number;
  readonly employee_id?: number;
  readonly original_filename?: string;
  readonly download_url?: string;
};

export type Employee = {
  readonly id: number;
  readonly personnel_number?: string;
  readonly name?: string;
  readonly birth_date?: string | null;
  readonly city?: string;
  readonly street?: string;
  readonly postal_code?: string;
  readonly department?: string;
  readonly shift_model?: string;
  readonly current_shift?: string;
  readonly team?: number | null;
  readonly salary_group?: string;
  readonly qualifications?: string;
  readonly favorite_machine?: string;
  readonly documents?: readonly EmployeeDocument[];
};

export type EmployeeDraft = {
  personnel_number: string;
  name: string;
  birth_date: string;
  city: string;
  street: string;
  postal_code: string;
  department: string;
  shift_model: string;
  current_shift: string;
  team: string;
  salary_group: string;
  favorite_machine: string;
  qualifications: string;
};

export type MessageState = {
  readonly text: string;
  readonly error: boolean;
};
