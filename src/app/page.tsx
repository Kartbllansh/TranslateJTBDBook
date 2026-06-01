import { BookReader } from "@/components/book-reader";
import { getBookChapters } from "@/lib/book-data";

export const dynamic = "force-static";

export default async function Home() {
  const chapters = await getBookChapters();

  return <BookReader chapters={chapters} />;
}
