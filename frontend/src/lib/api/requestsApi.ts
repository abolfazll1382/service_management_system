import type { DepartmentId } from "@/types/department";
import type { RequestPage, RequestQuery, ServiceRequest } from "@/types/request";
import type { ActorRef } from "@/types/user";
import * as server from "@/lib/mock-server/requests";
import type { CreateRequestInput, MessageInput, TransitionInput } from "@/lib/validation/request";
import { mockRequest } from "./mockClient";

export const requestsApi = {
  /* customer */
  create: (input: CreateRequestInput): Promise<ServiceRequest> => mockRequest((ctx) => server.createRequest(ctx, input)),
  listMine: (): Promise<ServiceRequest[]> => mockRequest((ctx) => server.listMyRequests(ctx)),

  /* staff */
  queue: (query: RequestQuery = {}): Promise<RequestPage> => mockRequest((ctx) => server.queueRequests(ctx, query)),
  transition: (requestId: string, input: TransitionInput): Promise<ServiceRequest> =>
    mockRequest((ctx) => server.transitionRequest(ctx, requestId, input)),
  assign: (requestId: string, assigneeId: string | null): Promise<ServiceRequest> =>
    mockRequest((ctx) => server.assignRequest(ctx, requestId, { assigneeId })),
  assignableStaff: (departmentId: DepartmentId): Promise<ActorRef[]> =>
    mockRequest((ctx) => server.assignableStaff(ctx, departmentId)),

  /* both — the server decides what each caller may read or post */
  get: (requestId: string): Promise<ServiceRequest> => mockRequest((ctx) => server.getRequest(ctx, requestId)),
  addMessage: (requestId: string, input: MessageInput): Promise<ServiceRequest> =>
    mockRequest((ctx) => server.addMessage(ctx, requestId, input)),
};
