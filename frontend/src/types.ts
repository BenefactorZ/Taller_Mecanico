export type Role = 'ADMINISTRADOR' | 'RECEPCIONISTA' | 'ASESOR_SERVICIO' | 'TECNICO' | 'CLIENTE' | 'SISTEMA'
export interface User { id: number; full_name: string; email: string; role: Role; branch: string | null; is_active: boolean }
