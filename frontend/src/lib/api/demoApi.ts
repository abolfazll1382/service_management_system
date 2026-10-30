import * as server from "@/lib/mock-server/demo";
import { mockRequest } from "./mockClient";

export const demoApi = {
  reset: (): Promise<void> => mockRequest((ctx) => server.resetDemo(ctx)),
};
