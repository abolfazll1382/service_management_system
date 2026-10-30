import { QueueView } from "@/features/console/QueueView";
import { titleFor } from "@/lib/i18n/page-metadata";

export const generateMetadata = () => titleFor("staff.overview.title");

export default function ConsoleHomePage() {
  return <QueueView />;
}
