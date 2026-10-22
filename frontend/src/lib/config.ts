export const IS_DEMO = process.env.NEXT_PUBLIC_DEMO_MODE === "true";
export const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/$/, "");
export const BUSY_MESSAGE = "Şu an çok yoğunuz, birkaç saniye sonra tekrar dene.";
