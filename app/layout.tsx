import "@fontsource/dm-sans/400.css";
import "@fontsource/dm-sans/500.css";
import "@fontsource/manrope/600.css";
import "@fontsource/manrope/700.css";
import "./globals.css";
import "./journey/journey.css";

export const metadata = {
  title: "NiyamCart — AI shopping, within your rules",
  description: "A bounded AI shopping agent with explainable recommendations and human-approved checkout.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
