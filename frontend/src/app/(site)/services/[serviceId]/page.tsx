import type { Metadata } from "next";
import { ServiceDetailView } from "@/features/catalog/ServiceDetailView";
import { findService } from "@/lib/catalog";
import { getServerLocale } from "@/lib/i18n/server";

// Next 16: dynamic route params arrive as a Promise.
type Params = { params: Promise<{ serviceId: string }> };

export async function generateMetadata({ params }: Params): Promise<Metadata> {
  const { serviceId } = await params;
  const service = findService(serviceId);
  return service ? { title: service.title[await getServerLocale()] } : {};
}

export default async function ServicePage({ params }: Params) {
  const { serviceId } = await params;
  return <ServiceDetailView serviceId={serviceId} />;
}
