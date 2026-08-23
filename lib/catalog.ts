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

const searchStopWords = new Set([
  "a", "all", "also", "and", "any", "anything", "color", "colour", "find", "for",
  "give", "i", "in", "is", "it", "looking", "maybe", "me", "need", "of", "please",
  "product", "products", "range", "recommend", "show", "some", "something", "that",
  "the", "to", "want", "with",
]);

const searchAliasGroups = [
  ["blue", "indigo", "navy", "azure", "cobalt"],
  ["red", "maroon", "berry", "rose", "burgundy", "crimson"],
  ["green", "emerald", "olive", "mint"],
  ["yellow", "saffron", "mustard", "gold"],
  ["purple", "violet", "plum", "lavender"],
  ["pink", "rose", "blush", "magenta"],
  ["black", "charcoal", "ebony"],
  ["white", "ivory", "cream"],
  ["washable", "wash", "washing"],
  ["bedsheet", "bedlinen", "sheet"],
  ["kids", "kid", "children", "child"],
  ["women", "woman", "female"],
  ["men", "man", "male"],
];

const normaliseSearchText = (value: unknown) =>
  String(value)
    .toLowerCase()
    .replaceAll("&", " and ")
    .match(/[a-z0-9]+/g)
    ?.join(" ") || "";

const pricePattern = String.raw`(?:rs\.?|inr|₹)?\s*([0-9][0-9,]*(?:\.[0-9]+)?)`;
const betweenPrice = new RegExp(
  String.raw`\bbetween\s*${pricePattern}\s*(?:and|to|-)\s*${pricePattern}`,
  "i",
);
const maximumPrice = new RegExp(
  String.raw`\b(?:under|below|less\s+than|up\s+to|upto|max(?:imum)?|within|budget(?:\s+of)?)\s*${pricePattern}`,
  "i",
);
const minimumPrice = new RegExp(
  String.raw`\b(?:above|over|more\s+than|at\s+least|min(?:imum)?)\s*${pricePattern}`,
  "i",
);

const parsePriceSearch = (query: string) => {
  let text = query;
  let minimum: number | null = null;
  let maximum: number | null = null;
  const between = text.match(betweenPrice);
  if (between) {
    const values = between.slice(1, 3).map((value) => Math.round(Number(value.replaceAll(",", "")) * 100));
    minimum = Math.min(...values);
    maximum = Math.max(...values);
    text = text.replace(betweenPrice, " ");
  }
  const upper = text.match(maximumPrice);
  if (upper) {
    maximum = Math.round(Number(upper[1].replaceAll(",", "")) * 100);
    text = text.replace(maximumPrice, " ");
  }
  const lower = text.match(minimumPrice);
  if (lower) {
    minimum = Math.round(Number(lower[1].replaceAll(",", "")) * 100);
    text = text.replace(minimumPrice, " ");
  }
  return { text, minimum, maximum };
};

const tokenVariants = (token: string) => {
  const variants = new Set([token]);
  searchAliasGroups.find((group) => group.includes(token))?.forEach((alias) => variants.add(alias));
  if (token.length > 4 && token.endsWith("ies")) variants.add(`${token.slice(0, -3)}y`);
  if (token.length > 4 && token.endsWith("es")) variants.add(token.slice(0, -2));
  if (token.length > 3 && token.endsWith("s")) variants.add(token.slice(0, -1));
  return [...variants];
};

const editDistance = (left: string, right: string) => {
  const row = Array.from({ length: right.length + 1 }, (_, index) => index);
  for (let i = 1; i <= left.length; i += 1) {
    let diagonal = row[0];
    row[0] = i;
    for (let j = 1; j <= right.length; j += 1) {
      const previous = row[j];
      row[j] = Math.min(row[j] + 1, row[j - 1] + 1, diagonal + (left[i - 1] === right[j - 1] ? 0 : 1));
      diagonal = previous;
    }
  }
  return row[right.length];
};

const matchesVariant = (variant: string, text: string, words: Set<string>) => {
  if (words.has(variant) || ` ${text} `.includes(` ${variant} `)) return true;
  if (variant.length < 6 || variant.includes(" ")) return false;
  const tolerance = variant.length >= 8 ? 2 : 1;
  return [...words].some(
    (word) => word.length >= 6 && editDistance(variant, word) <= tolerance,
  );
};

export const productSearchScore = (product: Product, query: string): number | null => {
  const { text, minimum, maximum } = parsePriceSearch(query);
  if (minimum !== null && product.pricePaise < minimum) return null;
  if (maximum !== null && product.pricePaise > maximum) return null;

  const groups = normaliseSearchText(text)
    .split(" ")
    .filter((token) => token && !searchStopWords.has(token))
    .map(tokenVariants);
  if (!groups.length) return 0;

  const rawFields: Record<string, unknown> = {
    name: product.name,
    productId: product.id,
    brand: product.brand,
    category: product.category,
    audience: product.audience,
    description: product.description,
    occasion: product.occasion,
    material: product.material,
    highlights: product.highlights.join(" "),
    badges: product.badges.join(" "),
    specifications: JSON.stringify(product.specs),
    sizeChart: `size chart ${JSON.stringify(product.sizeChart || {})}`,
    price: `${product.pricePaise / 100} rupees ${product.pricePaise} paise`,
    rating: `${product.rating} rating ${product.reviews} reviews`,
    stock: `${product.stock} in stock`,
    delivery: `${product.deliveryDays} days ${product.freeDelivery ? "free" : "paid"} delivery`,
    returns: `${product.returnWindowDays} day returns`,
  };
  const weights: Record<string, number> = {
    name: 12, productId: 12, category: 9, material: 9, occasion: 8, specifications: 8,
    sizeChart: 8, brand: 7, audience: 7, highlights: 5, badges: 5, description: 4,
    price: 4, rating: 2, stock: 2, delivery: 3, returns: 3,
  };
  const fields = Object.entries(rawFields).map(([name, value]) => {
    const normalised = normaliseSearchText(value);
    return { name, normalised, words: new Set(normalised.split(" ")) };
  });
  let score = 0;
  for (const group of groups) {
    const matches = fields.filter((field) =>
      group.some((variant) => matchesVariant(variant, field.normalised, field.words)),
    );
    if (!matches.length) return null;
    score += Math.max(...matches.map((field) => weights[field.name] || 1));
  }
  if (normaliseSearchText(text) && normaliseSearchText(product.name).includes(normaliseSearchText(text))) {
    score += 15;
  }
  return score;
};

export const searchProducts = (items: Product[], query: string) => {
  const searchableQuery = normaliseSearchText(parsePriceSearch(query).text);
  const results = items
    .map((product) => ({ product, score: productSearchScore(product, query) }))
    .filter((result): result is { product: Product; score: number } => result.score !== null)
    .sort((left, right) => right.score - left.score || right.product.rating - left.product.rating);
  const exact = results.filter(
    ({ product }) => normaliseSearchText(product.name) === searchableQuery,
  );
  return (exact.length ? exact : results).map((result) => result.product);
};
