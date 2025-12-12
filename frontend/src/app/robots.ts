import { MetadataRoute } from "next";

export default function robots(): MetadataRoute.Robots {
  const baseUrl = "https://smartplayfpl.com";

  return {
    rules: [
      {
        userAgent: "*",
        allow: "/",
        disallow: ["/api/", "/private/"],
      },
      // Google Search
      {
        userAgent: "Googlebot",
        allow: "/",
        disallow: ["/api/", "/private/"],
      },
      // Bing
      {
        userAgent: "Bingbot",
        allow: "/",
        disallow: ["/api/", "/private/"],
      },
      // GPTBot (OpenAI)
      {
        userAgent: "GPTBot",
        allow: "/",
        disallow: ["/api/", "/private/"],
      },
      // ChatGPT-User (OpenAI browsing)
      {
        userAgent: "ChatGPT-User",
        allow: "/",
        disallow: ["/api/", "/private/"],
      },
      // Google-Extended (Bard/Gemini training)
      {
        userAgent: "Google-Extended",
        allow: "/",
        disallow: ["/api/", "/private/"],
      },
      // Anthropic Claude
      {
        userAgent: "anthropic-ai",
        allow: "/",
        disallow: ["/api/", "/private/"],
      },
      {
        userAgent: "Claude-Web",
        allow: "/",
        disallow: ["/api/", "/private/"],
      },
      // Perplexity AI
      {
        userAgent: "PerplexityBot",
        allow: "/",
        disallow: ["/api/", "/private/"],
      },
      // Cohere AI
      {
        userAgent: "cohere-ai",
        allow: "/",
        disallow: ["/api/", "/private/"],
      },
      // Facebook
      {
        userAgent: "facebookexternalhit",
        allow: "/",
      },
      // Twitter
      {
        userAgent: "Twitterbot",
        allow: "/",
      },
      // LinkedIn
      {
        userAgent: "LinkedInBot",
        allow: "/",
      },
      // Slack
      {
        userAgent: "Slackbot",
        allow: "/",
      },
      // Discord
      {
        userAgent: "Discordbot",
        allow: "/",
      },
      // Telegram
      {
        userAgent: "TelegramBot",
        allow: "/",
      },
      // WhatsApp
      {
        userAgent: "WhatsApp",
        allow: "/",
      },
    ],
    sitemap: `${baseUrl}/sitemap.xml`,
    host: baseUrl,
  };
}
