import { MetadataRoute } from "next";

export default function sitemap(): MetadataRoute.Sitemap {
  const baseUrl = "https://smartplayfpl.com";
  const currentDate = new Date().toISOString();

  // Main pages - static routes
  const staticPages: MetadataRoute.Sitemap = [
    {
      url: baseUrl,
      lastModified: currentDate,
      changeFrequency: "daily",
      priority: 1.0,
    },
    {
      url: `${baseUrl}/my-team`,
      lastModified: currentDate,
      changeFrequency: "daily",
      priority: 0.9,
    },
    {
      url: `${baseUrl}/players`,
      lastModified: currentDate,
      changeFrequency: "daily",
      priority: 0.9,
    },
    {
      url: `${baseUrl}/build`,
      lastModified: currentDate,
      changeFrequency: "weekly",
      priority: 0.8,
    },
    {
      url: `${baseUrl}/model`,
      lastModified: currentDate,
      changeFrequency: "weekly",
      priority: 0.7,
    },
  ];

  // Strategy-based build pages
  const strategies = [
    "balanced",
    "template",
    "differential",
    "form",
    "value",
    "fixture",
  ];

  const strategyPages: MetadataRoute.Sitemap = strategies.map((strategy) => ({
    url: `${baseUrl}/build/${strategy}`,
    lastModified: currentDate,
    changeFrequency: "weekly" as const,
    priority: 0.7,
  }));

  // Custom build page
  const customBuild: MetadataRoute.Sitemap = [
    {
      url: `${baseUrl}/build/custom`,
      lastModified: currentDate,
      changeFrequency: "weekly",
      priority: 0.7,
    },
  ];

  return [...staticPages, ...strategyPages, ...customBuild];
}
