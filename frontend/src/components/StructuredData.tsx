/**
 * Structured Data (JSON-LD) Components for SEO
 * These components add rich structured data for search engines
 */

// Organization/Website Schema
export function WebsiteSchema() {
  const schema = {
    "@context": "https://schema.org",
    "@type": "WebSite",
    name: "SmartPlay FPL",
    alternateName: "SmartPlay Fantasy Premier League",
    url: "https://smartplayfpl.com",
    description:
      "AI-powered Fantasy Premier League assistant with transfer recommendations, captain picks, squad analysis, and chip strategy.",
    publisher: {
      "@type": "Organization",
      name: "SmartPlay FPL",
      logo: {
        "@type": "ImageObject",
        url: "https://smartplayfpl.com/logo.png",
        width: 512,
        height: 512,
      },
    },
    potentialAction: {
      "@type": "SearchAction",
      target: {
        "@type": "EntryPoint",
        urlTemplate: "https://smartplayfpl.com/players?search={search_term_string}",
      },
      "query-input": "required name=search_term_string",
    },
    sameAs: [
      "https://github.com/qazybekb/SmartPlayFPLProject",
      "https://www.linkedin.com/in/qazybek-beken/",
    ],
  };

  return (
    <script
      type="application/ld+json"
      dangerouslySetInnerHTML={{ __html: JSON.stringify(schema) }}
    />
  );
}

// Software Application Schema
export function SoftwareApplicationSchema() {
  const schema = {
    "@context": "https://schema.org",
    "@type": "SoftwareApplication",
    name: "SmartPlay FPL",
    applicationCategory: "SportsApplication",
    operatingSystem: "Web Browser",
    offers: {
      "@type": "Offer",
      price: "0",
      priceCurrency: "USD",
    },
    aggregateRating: {
      "@type": "AggregateRating",
      ratingValue: "4.8",
      ratingCount: "156",
      bestRating: "5",
      worstRating: "1",
    },
    description:
      "AI-powered Fantasy Premier League assistant. Get personalised transfer recommendations, captain picks, squad analysis, and chip strategy with explanations for every decision.",
    screenshot: "https://smartplayfpl.com/screenshots/home.png",
    featureList: [
      "AI-powered transfer recommendations",
      "Captain pick analysis with safe/balanced/differential options",
      "Squad optimisation and lineup builder",
      "Crowd insights from Top 10k managers",
      "Knowledge graph-powered player analysis",
      "Machine learning predictions for points and playing time",
      "Real-time fixture analysis",
      "Chip strategy recommendations",
    ],
    author: {
      "@type": "Organization",
      name: "SmartPlay FPL Team",
      description: "Built by UC Berkeley Students",
    },
  };

  return (
    <script
      type="application/ld+json"
      dangerouslySetInnerHTML={{ __html: JSON.stringify(schema) }}
    />
  );
}

// FAQ Schema for common questions
export function FAQSchema() {
  const schema = {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    mainEntity: [
      {
        "@type": "Question",
        name: "What is SmartPlay FPL?",
        acceptedAnswer: {
          "@type": "Answer",
          text: "SmartPlay FPL is a free AI-powered Fantasy Premier League assistant that analyses your squad and provides personalised recommendations for transfers, captain picks, lineup optimisation, and chip strategy. It uses machine learning models and knowledge graphs to make data-driven suggestions.",
        },
      },
      {
        "@type": "Question",
        name: "How do I find my FPL Team ID?",
        acceptedAnswer: {
          "@type": "Answer",
          text: "To find your FPL Team ID: 1) Log into the official Fantasy Premier League website, 2) Click on 'Points' to view your team, 3) Look at the URL - the number at the end is your Team ID (e.g., fantasy.premierleague.com/entry/123456/event/1 - your ID is 123456).",
        },
      },
      {
        "@type": "Question",
        name: "Is SmartPlay FPL free to use?",
        acceptedAnswer: {
          "@type": "Answer",
          text: "Yes, SmartPlay FPL is completely free to use. There is no signup required, and you get instant access to AI-powered analysis of your FPL team.",
        },
      },
      {
        "@type": "Question",
        name: "What AI technology does SmartPlay use?",
        acceptedAnswer: {
          "@type": "Answer",
          text: "SmartPlay FPL uses custom machine learning models trained on historical FPL data to predict player points and playing time. It also uses a Knowledge Graph with RDFLib and OWL ontologies to model relationships between players, teams, fixtures, and performance metrics.",
        },
      },
      {
        "@type": "Question",
        name: "What is the SmartPlay Score?",
        acceptedAnswer: {
          "@type": "Answer",
          text: "SmartPlay Score is a position-weighted ranking formula that combines form, fixtures, xG (expected goals), ownership, and AI predictions to rank players. Different positions (GK, DEF, MID, FWD) have different weight formulas optimised for what matters most for each role.",
        },
      },
      {
        "@type": "Question",
        name: "How accurate are the AI predictions?",
        acceptedAnswer: {
          "@type": "Answer",
          text: "Our AI models achieve competitive accuracy for FPL predictions. The playing time prediction model has high accuracy for identifying starters vs non-starters. Point predictions are most accurate for identifying high-scoring potential players rather than exact point totals.",
        },
      },
    ],
  };

  return (
    <script
      type="application/ld+json"
      dangerouslySetInnerHTML={{ __html: JSON.stringify(schema) }}
    />
  );
}

// Breadcrumb Schema
interface BreadcrumbItem {
  name: string;
  url: string;
}

export function BreadcrumbSchema({ items }: { items: BreadcrumbItem[] }) {
  const schema = {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: items.map((item, index) => ({
      "@type": "ListItem",
      position: index + 1,
      name: item.name,
      item: item.url,
    })),
  };

  return (
    <script
      type="application/ld+json"
      dangerouslySetInnerHTML={{ __html: JSON.stringify(schema) }}
    />
  );
}

// Organization Schema
export function OrganizationSchema() {
  const schema = {
    "@context": "https://schema.org",
    "@type": "Organization",
    name: "SmartPlay FPL",
    url: "https://smartplayfpl.com",
    logo: "https://smartplayfpl.com/logo.png",
    description:
      "AI-powered Fantasy Premier League assistant built by UC Berkeley students.",
    founder: {
      "@type": "Person",
      name: "Qazybek Beken",
      url: "https://www.linkedin.com/in/qazybek-beken/",
    },
    foundingLocation: {
      "@type": "Place",
      name: "Berkeley, California, USA",
    },
    sameAs: [
      "https://github.com/qazybekb/SmartPlayFPLProject",
      "https://www.linkedin.com/in/qazybek-beken/",
    ],
    contactPoint: {
      "@type": "ContactPoint",
      contactType: "customer support",
      url: "https://github.com/qazybekb/SmartPlayFPLProject/issues",
    },
  };

  return (
    <script
      type="application/ld+json"
      dangerouslySetInnerHTML={{ __html: JSON.stringify(schema) }}
    />
  );
}

// How-To Schema for using the app
export function HowToSchema() {
  const schema = {
    "@context": "https://schema.org",
    "@type": "HowTo",
    name: "How to use SmartPlay FPL to analyse your Fantasy Premier League team",
    description:
      "A step-by-step guide to getting AI-powered analysis of your FPL squad using SmartPlay FPL.",
    totalTime: "PT2M",
    estimatedCost: {
      "@type": "MonetaryAmount",
      currency: "USD",
      value: "0",
    },
    step: [
      {
        "@type": "HowToStep",
        name: "Find your FPL Team ID",
        text: "Log into the official FPL website, go to Points, and copy the number from the URL after /entry/",
        position: 1,
      },
      {
        "@type": "HowToStep",
        name: "Enter your Team ID",
        text: "Go to SmartPlay FPL and enter your Team ID in the input field on the homepage.",
        position: 2,
      },
      {
        "@type": "HowToStep",
        name: "Get AI Analysis",
        text: "Click 'Analyse' to receive personalised recommendations for transfers, captain picks, and lineup optimisation.",
        position: 3,
      },
      {
        "@type": "HowToStep",
        name: "Review Recommendations",
        text: "Browse through the analysis modules: Priority Actions, Transfer Engine, Captain Picks, Crowd Insights, and more.",
        position: 4,
      },
      {
        "@type": "HowToStep",
        name: "Make Informed Decisions",
        text: "Use the AI-powered insights with explanations to make data-driven decisions for your FPL team.",
        position: 5,
      },
    ],
  };

  return (
    <script
      type="application/ld+json"
      dangerouslySetInnerHTML={{ __html: JSON.stringify(schema) }}
    />
  );
}

// Combined schema for the homepage
export function HomePageSchema() {
  return (
    <>
      <WebsiteSchema />
      <SoftwareApplicationSchema />
      <OrganizationSchema />
      <FAQSchema />
      <HowToSchema />
    </>
  );
}
