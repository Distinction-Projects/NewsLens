import TextAnalyzeForm from "../../components/TextAnalyzeForm";

export const dynamic = "force-dynamic";

export default function TextPage() {
  return (
    <main className="text-page">
      <section className="panel text-hero">
        <p className="section-kicker">Interactive Analysis</p>
        <h1>Test Your Own Text</h1>
        <p className="muted">
          Run a focused sentiment pass against the app&apos;s supported local models and inspect the immediate score output.
        </p>
      </section>

      <TextAnalyzeForm />
    </main>
  );
}
