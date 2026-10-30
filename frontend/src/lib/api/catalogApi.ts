import type { ServiceListing } from "@/types/service";
import * as server from "@/lib/mock-server/catalog";
import { mockRequest } from "./mockClient";

export const catalogApi = {
  listServices: (): Promise<ServiceListing[]> => mockRequest(() => server.listServices()),
  getService: (serviceId: string): Promise<ServiceListing> => mockRequest(() => server.getService(serviceId)),
  setServiceActive: (serviceId: string, isActive: boolean): Promise<ServiceListing> =>
    mockRequest((ctx) => server.setServiceActive(ctx, serviceId, isActive)),
};
