export type Product = {
  id: string;
  name: string;
  category: string;
  description: string;
  pricePaise: number;
  originalPricePaise?: number;
  rating: number;
  reviews: number;
  badge?: string;
  accent: string;
  emoji: string;
  stock: number;
  tags: string[];
};

export const products: Product[] = [
  {
    id: "orbit-headphones",
    name: "Orbit ANC Headphones",
    category: "Audio",
    description: "40-hour battery, adaptive noise cancellation and multipoint pairing.",
    pricePaise: 649900,
    originalPricePaise: 799900,
    rating: 4.8,
    reviews: 824,
    badge: "Best match",
    accent: "#dff6ec",
    emoji: "🎧",
    stock: 12,
    tags: ["work", "travel", "wireless"],
  },
  {
    id: "arc-keyboard",
    name: "Arc Mechanical Keyboard",
    category: "Workspace",
    description: "Low-profile tactile keys, quiet switches and three-device pairing.",
    pricePaise: 429900,
    originalPricePaise: 499900,
    rating: 4.6,
    reviews: 391,
    badge: "Popular",
    accent: "#f4eadc",
    emoji: "⌨️",
    stock: 7,
    tags: ["work", "productivity", "wireless"],
  },
  {
    id: "beam-lamp",
    name: "Beam Focus Lamp",
    category: "Workspace",
    description: "Flicker-free desk lighting with ambient sensor and USB-C charging.",
    pricePaise: 249900,
    rating: 4.7,
    reviews: 216,
    badge: "Smart add-on",
    accent: "#e8e6fa",
    emoji: "💡",
    stock: 18,
    tags: ["work", "lighting", "usb-c"],
  },
  {
    id: "loop-stand",
    name: "Loop Laptop Stand",
    category: "Workspace",
    description: "Foldable aluminium stand with six height levels and travel sleeve.",
    pricePaise: 159900,
    originalPricePaise: 199900,
    rating: 4.5,
    reviews: 508,
    accent: "#e0eef8",
    emoji: "💻",
    stock: 23,
    tags: ["work", "ergonomic", "travel"],
  },
  {
    id: "pulse-speaker",
    name: "Pulse Mini Speaker",
    category: "Audio",
    description: "Pocket-sized waterproof speaker with stereo pairing and 14-hour playtime.",
    pricePaise: 299900,
    rating: 4.4,
    reviews: 672,
    accent: "#f8e3e3",
    emoji: "🔊",
    stock: 9,
    tags: ["travel", "wireless", "waterproof"],
  },
  {
    id: "carry-sleeve",
    name: "Carry Recycled Sleeve",
    category: "Accessories",
    description: "Water-resistant 14-inch sleeve made from recycled fabric.",
    pricePaise: 119900,
    rating: 4.6,
    reviews: 144,
    accent: "#eef0dd",
    emoji: "👜",
    stock: 31,
    tags: ["travel", "laptop", "sustainable"],
  },
];

export const formatMoney = (paise: number) =>
  new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  }).format(paise / 100);
