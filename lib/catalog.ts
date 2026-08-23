import catalog from "@/backend/data/catalog.json";

type CatalogRecord = {
  id: string;
  name: string;
  brand: string;
  category: string;
  audience: string;
  description: string;
  pricePaise: number;
  originalPricePaise: number;
  rating: number;
  reviews: number;
  stock: number;
  deliveryDays: number;
  freeDelivery: boolean;
  occasion: string;
  material: string;
  highlights: string[];
  badges: string[];
  specs: Record<string, string | number | boolean>;
  sizeChart: Record<string, Record<string, number>> | null;
  returnWindowDays: number;
  image: string;
};

export type Product = CatalogRecord & {
  badge?: string;
  accent: string;
  tags: string[];
};

const accents = ["#dff6ec", "#f4eadc", "#e8e6fa", "#e0eef8", "#f8e3e3", "#eef0dd"];
const categoryAccents = new Map(
  Array.from(new Set((catalog as unknown as CatalogRecord[]).map((item) => item.category))).map(
    (category, index) => [category, accents[index % accents.length]],
  ),
);

export const products: Product[] = (catalog as unknown as CatalogRecord[]).map((item) => ({
  ...item,
  badge: item.badges[0],
  accent: categoryAccents.get(item.category) || accents[0],
  tags: [item.audience, item.occasion, item.material, ...item.highlights, ...item.badges],
}));

export const formatMoney = (paise: number) =>
  new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  }).format(paise / 100);

export const formatSpecLabel = (key: string) =>
  key
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
