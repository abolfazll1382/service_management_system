import type { AuthResult } from "@/types/api";
import type { PublicUser } from "@/types/user";
import * as server from "@/lib/mock-server/auth";
import type { CustomerLoginInput, RegisterInput, StaffLoginInput } from "@/lib/validation/auth";
import { mockRequest } from "./mockClient";

export const authApi = {
  register: (input: RegisterInput): Promise<AuthResult> => mockRequest(() => server.register(input)),
  loginCustomer: (input: CustomerLoginInput): Promise<AuthResult> => mockRequest(() => server.loginCustomer(input)),
  loginStaff: (input: StaffLoginInput): Promise<AuthResult> => mockRequest(() => server.loginStaff(input)),
  /** Call BEFORE clearing the local session: the token is read when the call is made. */
  logout: (): Promise<void> => mockRequest((ctx) => server.logout(ctx)),
  me: (): Promise<PublicUser> => mockRequest((ctx) => server.currentUser(ctx)),
};
