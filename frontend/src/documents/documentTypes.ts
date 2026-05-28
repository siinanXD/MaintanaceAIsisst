export type Machine = {
  readonly id: number;
  readonly name: string;
};

export type GeneratedDocument = {
  readonly id: number;
  readonly task_id?: number;
  readonly title?: string;
  readonly department?: string;
  readonly machine?: string;
  readonly machine_id?: number | null;
  readonly status?: string;
  readonly version?: number | null;
  readonly summary?: string;
  readonly summary_status?: string;
  readonly quality_score?: number | null;
  readonly quality_status?: string;
  readonly created_at?: string;
  readonly download_url?: string;
  readonly pdf_url?: string;
};

export type MachineManual = {
  readonly id: number;
  readonly machine_id?: number | null;
  readonly machine?: Machine | null;
  readonly department?: string;
  readonly title?: string;
  readonly original_filename?: string;
  readonly analysis?: string;
  readonly analysis_status?: string;
  readonly summary?: string;
  readonly summary_status?: string;
  readonly version?: number | null;
  readonly created_at?: string;
  readonly download_url?: string;
};

export type DocumentFilters = {
  readonly task_id: string;
  readonly department: string;
  readonly machine: string;
  readonly date_from: string;
  readonly date_to: string;
};

export type MessageState = {
  readonly text: string;
  readonly error: boolean;
};

export type DocumentReview = {
  readonly document?: {
    readonly title?: string;
    readonly filename?: string;
    readonly source?: string;
    readonly document_type?: string;
  };
  readonly quality_score?: number;
  readonly status?: string;
  readonly findings?: readonly ReviewFinding[];
  readonly checks?: readonly ReviewFinding[];
  readonly recommendations?: readonly string[];
};

export type ReviewFinding = {
  readonly field?: string;
  readonly message?: string;
  readonly severity?: string;
};

export type DocumentSummary = {
  readonly title?: string;
  readonly summary_status?: string;
  readonly analysis_status?: string;
  readonly summary?: string;
  readonly analysis?: string;
};

export type DocumentVersion = {
  readonly id: number;
  readonly version_number: number;
  readonly created_at?: string;
};
