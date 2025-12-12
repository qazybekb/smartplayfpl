"use client";

import { useState, useRef, useEffect } from "react";
import { MessageCircle, X, Send, Sparkles, ChevronRight, Trash2 } from "lucide-react";

interface Message {
  id: string;
  type: "user" | "bot";
  text: string;
  players?: any[];
  action?: {
    type: "filter" | "compare" | "view";
    label: string;
    onClick: () => void;
  };
}

interface TemplateQuery {
  id: string;
  icon: string;
  text: string;
  shortText: string;
}

const TEMPLATE_QUERIES: TemplateQuery[] = [
  {
    id: "captain",
    icon: "👑",
    text: "Who should I captain this week?",
    shortText: "Best captain picks",
  },
  {
    id: "differential",
    icon: "💎",
    text: "Show me differentials under 5% ownership",
    shortText: "Find differentials",
  },
  {
    id: "budget",
    icon: "💰",
    text: "Best budget midfielders under £6m",
    shortText: "Budget options",
  },
  {
    id: "fixtures",
    icon: "🟢",
    text: "Who has the easiest fixtures?",
    shortText: "Easy fixtures",
  },
  {
    id: "inform",
    icon: "🔥",
    text: "Which players are in the best form?",
    shortText: "In-form players",
  },
];

interface ChatWidgetProps {
  allPlayers: any[];
  onApplyFilter: (filters: any) => void;
  onSelectPlayer: (player: any) => void;
}

export default function ChatWidget({ allPlayers, onApplyFilter, onSelectPlayer }: ChatWidgetProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputValue, setInputValue] = useState("");
  const [isTyping, setIsTyping] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Process query and generate response
  const processQuery = (query: string): Message => {
    const lowerQuery = query.toLowerCase();
    
    // Captain query
    if (lowerQuery.includes("captain")) {
      const captainPicks = allPlayers
        .filter(p => p.form >= 6 && p.status === "a")
        .sort((a, b) => b.form - a.form)
        .slice(0, 5);
      
      return {
        id: Date.now().toString(),
        type: "bot",
        text: `👑 **Top captain picks this week:**\n\n${captainPicks.map((p, i) => 
          `${i + 1}. **${p.webName}** (${p.teamShort}) - Form: ${p.form.toFixed(1)}, £${p.price.toFixed(1)}m`
        ).join("\n")}`,
        players: captainPicks,
        action: {
          type: "filter",
          label: "Show Captain Candidates",
          onClick: () => onApplyFilter({ inferredClasses: ["CaptainCandidate"] }),
        },
      };
    }
    
    // Differential query
    if (lowerQuery.includes("differential") || lowerQuery.includes("low owned") || lowerQuery.includes("under 5%")) {
      const differentials = allPlayers
        .filter(p => p.ownership < 5 && p.form >= 4 && p.status === "a")
        .sort((a, b) => b.form - a.form)
        .slice(0, 5);
      
      return {
        id: Date.now().toString(),
        type: "bot",
        text: `💎 **Hidden gems under 5% ownership:**\n\n${differentials.map((p, i) => 
          `${i + 1}. **${p.webName}** (${p.teamShort}) - ${p.ownership.toFixed(1)}% owned, Form: ${p.form.toFixed(1)}`
        ).join("\n")}`,
        players: differentials,
        action: {
          type: "filter",
          label: "Show All Differentials",
          onClick: () => onApplyFilter({ ownershipRange: [0, 5], formRange: [4, 10] }),
        },
      };
    }
    
    // Budget midfielders query
    if ((lowerQuery.includes("budget") || lowerQuery.includes("cheap")) && lowerQuery.includes("mid")) {
      const budgetMids = allPlayers
        .filter(p => p.position === "MID" && p.price < 6 && p.form >= 3)
        .sort((a, b) => b.form - a.form)
        .slice(0, 5);
      
      return {
        id: Date.now().toString(),
        type: "bot",
        text: `💰 **Best budget midfielders under £6m:**\n\n${budgetMids.map((p, i) => 
          `${i + 1}. **${p.webName}** (${p.teamShort}) - £${p.price.toFixed(1)}m, Form: ${p.form.toFixed(1)}`
        ).join("\n")}`,
        players: budgetMids,
        action: {
          type: "filter",
          label: "Filter Budget Mids",
          onClick: () => onApplyFilter({ positions: ["MID"], priceRange: [3.5, 6] }),
        },
      };
    }
    
    // Easy fixtures query
    if (lowerQuery.includes("fixture") || lowerQuery.includes("easy")) {
      const easyFixtures = allPlayers
        .filter(p => p.avgFDR && p.avgFDR <= 2.5 && p.form >= 4)
        .sort((a, b) => (a.avgFDR || 5) - (b.avgFDR || 5))
        .slice(0, 5);
      
      return {
        id: Date.now().toString(),
        type: "bot",
        text: `🟢 **Players with easiest fixtures:**\n\n${easyFixtures.map((p, i) => 
          `${i + 1}. **${p.webName}** (${p.teamShort}) - FDR: ${p.avgFDR?.toFixed(1) || "N/A"}, Form: ${p.form.toFixed(1)}`
        ).join("\n")}`,
        players: easyFixtures,
        action: {
          type: "filter",
          label: "Show Easy Fixtures",
          onClick: () => onApplyFilter({ fdrRange: [1, 2.5] }),
        },
      };
    }
    
    // In-form query
    if (lowerQuery.includes("form") || lowerQuery.includes("hot") || lowerQuery.includes("fire")) {
      const inForm = allPlayers
        .filter(p => p.form >= 6 && p.status === "a")
        .sort((a, b) => b.form - a.form)
        .slice(0, 5);
      
      return {
        id: Date.now().toString(),
        type: "bot",
        text: `🔥 **Players in the best form:**\n\n${inForm.map((p, i) => 
          `${i + 1}. **${p.webName}** (${p.teamShort}) - Form: ${p.form.toFixed(1)}, ${p.totalPoints} pts`
        ).join("\n")}`,
        players: inForm,
        action: {
          type: "filter",
          label: "Show All In-Form",
          onClick: () => onApplyFilter({ formRange: [6, 10] }),
        },
      };
    }
    
    // Default response
    return {
      id: Date.now().toString(),
      type: "bot",
      text: "I can help you find players! Try asking about:\n\n• Captain picks\n• Differentials\n• Budget options\n• Players with easy fixtures\n• In-form players",
    };
  };

  const handleSend = (text: string) => {
    if (!text.trim()) return;
    
    // Add user message
    const userMessage: Message = {
      id: Date.now().toString(),
      type: "user",
      text: text,
    };
    setMessages(prev => [...prev, userMessage]);
    setInputValue("");
    setIsTyping(true);
    
    // Simulate typing delay
    setTimeout(() => {
      const response = processQuery(text);
      setMessages(prev => [...prev, response]);
      setIsTyping(false);
    }, 500);
  };

  const handleTemplateClick = (template: TemplateQuery) => {
    handleSend(template.text);
  };

  return (
    <>
      {/* Floating Button */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className={`fixed bottom-6 right-6 z-50 w-14 h-14 rounded-full shadow-lg transition-all duration-300 flex items-center justify-center ${
          isOpen 
            ? "bg-slate-700 hover:bg-slate-800 rotate-0" 
            : "bg-gradient-to-r from-violet-500 to-purple-600 hover:from-violet-600 hover:to-purple-700 shadow-violet-500/30"
        }`}
      >
        {isOpen ? (
          <X className="w-6 h-6 text-white" />
        ) : (
          <MessageCircle className="w-6 h-6 text-white" />
        )}
      </button>

      {/* Chat Panel */}
      {isOpen && (
        <div className="fixed bottom-24 right-6 z-50 w-[360px] max-h-[500px] bg-white rounded-2xl shadow-2xl border border-slate-200 overflow-hidden flex flex-col animate-in slide-in-from-bottom-5 duration-300">
          {/* Header */}
          <div className="px-4 py-3 bg-gradient-to-r from-violet-500 to-purple-600 text-white">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Sparkles className="w-5 h-5" />
                <div>
                  <h3 className="font-semibold text-sm">FPL Assistant</h3>
                  <p className="text-[10px] text-white/80">Powered by Knowledge Graph</p>
                </div>
              </div>
              {messages.length > 0 && (
                <button
                  onClick={() => setMessages([])}
                  className="p-1.5 rounded-lg hover:bg-white/20 transition-colors"
                  title="Clear chat"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              )}
            </div>
          </div>

          {/* Messages */}
          <div className="flex-1 overflow-y-auto p-4 space-y-3 min-h-[200px] max-h-[300px]">
            {messages.length === 0 ? (
              <div className="text-center py-4">
                <p className="text-sm text-slate-500 mb-4">Ask me anything about FPL players!</p>
                <div className="space-y-2">
                  {TEMPLATE_QUERIES.map((template) => (
                    <button
                      key={template.id}
                      onClick={() => handleTemplateClick(template)}
                      className="w-full flex items-center gap-2 px-3 py-2 text-left text-sm bg-slate-50 hover:bg-violet-50 border border-slate-200 hover:border-violet-300 rounded-xl transition-colors group"
                    >
                      <span className="text-lg">{template.icon}</span>
                      <span className="flex-1 text-slate-700 group-hover:text-violet-700">{template.shortText}</span>
                      <ChevronRight className="w-4 h-4 text-slate-400 group-hover:text-violet-500" />
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              <>
                {messages.map((message) => (
                  <div
                    key={message.id}
                    className={`flex ${message.type === "user" ? "justify-end" : "justify-start"}`}
                  >
                    <div
                      className={`max-w-[85%] rounded-2xl px-3 py-2 ${
                        message.type === "user"
                          ? "bg-violet-500 text-white rounded-br-md"
                          : "bg-slate-100 text-slate-800 rounded-bl-md"
                      }`}
                    >
                      <p className="text-sm whitespace-pre-line">{message.text.replace(/\*\*/g, "")}</p>
                      {message.action && (
                        <button
                          onClick={() => {
                            message.action?.onClick();
                            setIsOpen(false);
                          }}
                          className="mt-2 w-full flex items-center justify-center gap-1 px-2 py-1.5 bg-violet-500 hover:bg-violet-600 text-white text-xs font-medium rounded-lg transition-colors"
                        >
                          {message.action.label}
                          <ChevronRight className="w-3 h-3" />
                        </button>
                      )}
                    </div>
                  </div>
                ))}
                {isTyping && (
                  <div className="flex justify-start">
                    <div className="bg-slate-100 rounded-2xl rounded-bl-md px-4 py-2">
                      <div className="flex gap-1">
                        <span className="w-2 h-2 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay: "0ms" }}></span>
                        <span className="w-2 h-2 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay: "150ms" }}></span>
                        <span className="w-2 h-2 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay: "300ms" }}></span>
                      </div>
                    </div>
                  </div>
                )}
                <div ref={messagesEndRef} />
              </>
            )}
          </div>

          {/* Input */}
          <div className="p-3 border-t border-slate-200 bg-slate-50">
            {messages.length > 0 && (
              <div className="flex gap-1 mb-2 overflow-x-auto pb-1">
                {TEMPLATE_QUERIES.slice(0, 3).map((template) => (
                  <button
                    key={template.id}
                    onClick={() => handleTemplateClick(template)}
                    className="flex-shrink-0 px-2 py-1 text-[10px] bg-white border border-slate-200 hover:border-violet-300 rounded-full text-slate-600 hover:text-violet-600 transition-colors"
                  >
                    {template.icon} {template.shortText}
                  </button>
                ))}
              </div>
            )}
            <div className="flex gap-2">
              <input
                type="text"
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleSend(inputValue)}
                placeholder="Ask about players..."
                className="flex-1 px-3 py-2 text-sm border border-slate-200 rounded-xl focus:border-violet-400 focus:ring-2 focus:ring-violet-400/20 outline-none"
              />
              <button
                onClick={() => handleSend(inputValue)}
                disabled={!inputValue.trim()}
                className="px-3 py-2 bg-violet-500 hover:bg-violet-600 disabled:bg-slate-300 text-white rounded-xl transition-colors"
              >
                <Send className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

