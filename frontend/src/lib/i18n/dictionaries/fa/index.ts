import type { Dictionary } from "../../types";
import { common } from "./common";
import { errors, validation } from "./feedback";
import { auth, catalog } from "./site";
import { request } from "./request";
import { staff } from "./staff";

export const fa: Dictionary = { common, errors, validation, auth, catalog, request, staff };
