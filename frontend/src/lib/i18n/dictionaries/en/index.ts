import { common } from "./common";
import { errors, validation } from "./feedback";
import { auth, catalog } from "./site";
import { request } from "./request";
import { staff } from "./staff";

export const en = { common, errors, validation, auth, catalog, request, staff } as const;
