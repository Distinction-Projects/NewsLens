import TextAnalyzeForm from "../../components/TextAnalyzeForm";

export const dynamic = "force-dynamic";

export default function TextPage() {
  return (
    <main>
      <h1>Test Your Own Text</h1>
      <p className="muted">Run sentiment analysis on custom text with Naive Bayes, SVM, or VADER.</p>
      <TextAnalyzeForm />
    </main>
  );
}
