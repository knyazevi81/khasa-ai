// Соответствуют ответам бэкенда (app/presentation/fastapi/schemas/schemas.py)

export interface UserDTO {
  id: string;
  email: string;
  is_active: boolean;
  is_email_verified: boolean;
  is_superuser: boolean;
}

export interface TokenPairDTO {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface UsersListDTO {
  users: UserDTO[];
  total: number;
}

export interface MessageDTO {
  message: string;
}

export interface ApiError {
  status: number;
  code: number;
  detail: string;
}
