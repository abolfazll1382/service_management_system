import type { StaffAccount, StaffProfile } from "@/types/user";
import * as server from "@/lib/mock-server/staff";
import type { CreateStaffInput, UpdateStaffInput } from "@/lib/validation/staff";
import { mockRequest } from "./mockClient";

export const staffApi = {
  list: (): Promise<StaffAccount[]> => mockRequest((ctx) => server.listStaff(ctx)),
  create: (input: CreateStaffInput): Promise<StaffProfile> => mockRequest((ctx) => server.createStaff(ctx, input)),
  update: (staffId: string, input: UpdateStaffInput): Promise<StaffProfile> =>
    mockRequest((ctx) => server.updateStaff(ctx, staffId, input)),
};
