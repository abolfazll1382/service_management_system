import { Suspense } from "react";
import { ServicesView } from "@/features/catalog/ServicesView";
import { titleFor } from "@/lib/i18n/page-metadata";

export const generateMetadata = () => titleFor("catalog.list.title");

export default function ServicesPage() {
  // useSearchParams (the department filter) needs a Suspense boundary above it.
  return (
    <Suspense>
      <ServicesView />
    </Suspense>
  );
}
