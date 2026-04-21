import "./globals.css";

export const metadata = {
  title: "NewsLens Node Frontend",
  description: "FastAPI-powered NewsLens frontend scaffold"
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
