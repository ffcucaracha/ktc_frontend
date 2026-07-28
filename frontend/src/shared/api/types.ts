export type UserRole = "admin" | "operator";

export interface ApiErrorBody {
  error: {
    code: string;
    message: string;
    details: Record<string, unknown>;
  };
}

export interface AccessTokenResponse {
  access_token: string;
  token_type: "bearer";
}

export interface User {
  id: string;
  username: string;
  full_name: string;
  role: UserRole;
  is_active: boolean;
}

export interface MeResponse {
  user: User;
}
