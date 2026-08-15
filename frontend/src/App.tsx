import { useState, useRef, useEffect, useCallback, lazy, Suspense } from 'react'
import {
  Send, Bot, User, Search, Code, FileText, Terminal, Brain,
  Sparkles, Plus, MessageSquare, Zap,
  Globe, FolderTree, Loader2, PanelLeftClose, PanelLeftOpen,
  Trash2, Settings, CheckCircle2, AlertCircle
} from 'lucide-react'

// Lazy-load the LLM config modal (only shown when user clicks settings)
const LLMConfigModal = lazy(() => import('./components/LLMConfigModal'))

// Types
interface ToolCall {
  id: string
  name: string
  arguments: Record<string, any>
  status: 'pending' | 'running' | 'completed' | 'failed'
  result?: string
  error?: string
}

interface Step {
  id: string
  description: string
  status: 'pending' | 'executing' | 'completed' | 'failed'
  tool_calls: ToolCall[]
}

interface Message {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  tool_calls?: ToolCall[]
  steps?: Step[]
  timestamp: string
  isStreaming?: boolean
}

interface Conversation {
  id: string
  title: string
  created_at: string
  message_count: number
}

// Tool icon mapping
const toolIcons: Record<string, any> = {
  web_search: Globe,
  execute_code: Code,
  file_manager: FolderTree,
  shell: Terminal,
  think: Brain,
}

// API helpers
const API_BASE = (import.meta.env.VITE_API_URL as string) || ''

async function apiPost(endpoint: string, data: any) {
  const token = localStorage.getItem('auth_token')
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }
  
  const res = await fetch(`${API_BASE}${endpoint}`, {
    method: 'POST',
    headers,
    body: JSON.stringify(data),
  })
  
  if (res.status === 401) {
    // Token expired or invalid - redirect to login
    localStorage.removeItem('auth_token')
    localStorage.removeItem('auth_user')
    window.location.href = '/login'
    throw new Error('Authentication required')
  }
  
  if (!res.ok) throw new Error(`API Error: ${res.statusText}`)
  return res.json()
}

async function apiGet(endpoint: string) {
  const token = localStorage.getItem('auth_token')
  const headers: Record<string, string> = {}
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }
  
  const res = await fetch(`${API_BASE}${endpoint}`, { headers })
  
  if (res.status === 401) {
    // Token expired or invalid - redirect to login
    localStorage.removeItem('auth_token')
    localStorage.removeItem('auth_user')
    window.location.href = '/login'
    throw new Error('Authentication required')
  }
  
  if (!res.ok) throw new Error(`API Error: ${res.statusText}`)
  return res.json()
}

// Components
function ToolCallBadge({ toolCall }: { toolCall: ToolCall }) {
  const Icon = toolIcons[toolCall.name] || Zap
  const statusColors = {
    pending: 'bg-gray-500/20 text-gray-400',
    running: 'bg-blue-500/20 text-blue-400 animate-pulse',
    completed: 'bg-emerald-500/20 text-emerald-400',
    failed: 'bg-red-500/20 text-red-400',
  }

  return (
    <div className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium ${statusColors[toolCall.status]}`}>
      <Icon size={12} />
      <span>{toolCall.name}</span>
      {toolCall.status === 'running' && <Loader2 size={10} className="animate-spin" />}
      {toolCall.status === 'completed' && <CheckCircle2 size={10} />}
      {toolCall.status === 'failed' && <AlertCircle size={10} />}
    </div>
  )
}

function StepIndicator({ step, index }: { step: Step; index: number }) {
  return (
    <div className="flex items-start gap-3 py-2">
      <div className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0 mt-0.5 ${
        step.status === 'completed' ? 'bg-emerald-500/20 text-emerald-400' :
        step.status === 'executing' ? 'bg-blue-500/20 text-blue-400 animate-pulse' :
        'bg-gray-500/20 text-gray-500'
      }`}>
        {step.status === 'completed' ? '✓' : index + 1}
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm text-gray-300">{step.description}</p>
        {step.tool_calls.length > 0 && (
          <div className="flex flex-wrap gap-1.5 mt-1.5">
            {step.tool_calls.map(tc => <ToolCallBadge key={tc.id} toolCall={tc} />)}
          </div>
        )}
      </div>
    </div>
  )
}

function MessageBubble({ message }: { message: Message }) {
  const isUser = message.role === 'user'

  return (
    <div className={`flex gap-3 px-4 py-4 ${isUser ? '' : 'bg-[#1a1a2e]/50'}`}>
      <div className={`w-8 h-8 rounded-xl flex items-center justify-center flex-shrink-0 ${
        isUser ? 'bg-gradient-to-br from-violet-500 to-purple-600' : 'bg-gradient-to-br from-cyan-500 to-blue-600'
      }`}>
        {isUser ? <User size={16} className="text-white" /> : <Bot size={16} className="text-white" />}
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1">
          <span className="text-xs font-semibold text-gray-400">
            {isUser ? 'You' : 'Celia'}
          </span>
          <span className="text-xs text-gray-600">
            {new Date(message.timestamp).toLocaleTimeString()}
          </span>
        </div>

        {/* Message content */}
        <div className="text-gray-200 text-sm leading-relaxed whitespace-pre-wrap">
          {message.content}
        </div>

        {/* Steps */}
        {message.steps && message.steps.length > 0 && (
          <div className="mt-3 border border-gray-700/50 rounded-xl overflow-hidden">
            <div className="bg-gray-800/50 px-3 py-2 border-b border-gray-700/50 flex items-center gap-2">
              <Sparkles size={12} className="text-cyan-400" />
              <span className="text-xs font-medium text-gray-400">Execution Plan</span>
            </div>
            <div className="p-3 space-y-1">
              {message.steps.map((step, i) => (
                <StepIndicator key={step.id} step={step} index={i} />
              ))}
            </div>
          </div>
        )}

        {/* Tool calls */}
        {message.tool_calls && message.tool_calls.length > 0 && !message.steps?.length && (
          <div className="flex flex-wrap gap-1.5 mt-2">
            {message.tool_calls.map(tc => <ToolCallBadge key={tc.id} toolCall={tc} />)}
          </div>
        )}

        {/* Streaming indicator */}
        {message.isStreaming && (
          <div className="flex items-center gap-2 mt-2">
            <div className="flex gap-1">
              <div className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-bounce" style={{ animationDelay: '0ms' }} />
              <div className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-bounce" style={{ animationDelay: '150ms' }} />
              <div className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-bounce" style={{ animationDelay: '300ms' }} />
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

// Sidebar Component
function Sidebar({
  conversations,
  activeId,
  onSelect,
  onNew,
  onDelete,
  isOpen,
  onToggle,
  llmStatus,
  onOpenConfig
}: {
  conversations: Conversation[]
  activeId?: string
  onSelect: (id: string) => void
  onNew: () => void
  onDelete: (id: string) => void
  isOpen: boolean
  onToggle: () => void
  llmStatus: any
  onOpenConfig: () => void
}) {
  return (
    <>
      {/* Toggle button */}
      <button
        onClick={onToggle}
        className="fixed top-4 left-4 z-50 p-2 rounded-lg bg-gray-800/80 hover:bg-gray-700 text-gray-400 hover:text-white transition-all backdrop-blur-sm border border-gray-700/50"
      >
        {isOpen ? <PanelLeftClose size={18} /> : <PanelLeftOpen size={18} />}
      </button>

      {/* Sidebar */}
      <div className={`fixed left-0 top-0 h-full z-40 transition-transform duration-300 ${
        isOpen ? 'translate-x-0' : '-translate-x-full'
      }`}>
        <div className="w-72 h-full bg-[#0d0d1a] border-r border-gray-800/50 flex flex-col">
          {/* Header */}
          <div className="p-4 border-b border-gray-800/50">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-cyan-500 to-blue-600 flex items-center justify-center">
                <Sparkles size={16} className="text-white" />
              </div>
              <div>
                <h1 className="text-sm font-bold text-white">celia.pro</h1>
                <p className="text-xs text-gray-500">AI Agent System v1.1</p>
              </div>
            </div>
            <button
              onClick={onNew}
              className="w-full flex items-center gap-2 px-3 py-2.5 rounded-xl bg-gradient-to-r from-cyan-500/10 to-blue-500/10 hover:from-cyan-500/20 hover:to-blue-500/20 border border-cyan-500/20 text-cyan-400 text-sm font-medium transition-all"
            >
              <Plus size={16} />
              محادثة جديدة
            </button>
          </div>

          {/* Conversations list */}
          <div className="flex-1 overflow-y-auto p-2">
            {conversations.length === 0 ? (
              <div className="text-center py-8 text-gray-600 text-xs">
                لا توجد محادثات سابقة
              </div>
            ) : (
              conversations.map(conv => (
                <div
                  key={conv.id}
                  onClick={() => onSelect(conv.id)}
                  className={`group flex items-center gap-2 px-3 py-2.5 rounded-xl cursor-pointer mb-1 transition-all ${
                    activeId === conv.id
                      ? 'bg-gray-800/80 text-white'
                      : 'text-gray-400 hover:bg-gray-800/40 hover:text-gray-300'
                  }`}
                >
                  <MessageSquare size={14} className="flex-shrink-0" />
                  <span className="text-sm truncate flex-1">{conv.title}</span>
                  <button
                    onClick={(e) => { e.stopPropagation(); onDelete(conv.id) }}
                    className="opacity-0 group-hover:opacity-100 p-1 hover:text-red-400 transition-all"
                  >
                    <Trash2 size={12} />
                  </button>
                </div>
              ))
            )}
          </div>

          {/* Footer - LLM Status */}
          <div className="p-4 border-t border-gray-800/50 space-y-2">
            <button
              onClick={onOpenConfig}
              className="w-full flex items-center gap-2 px-3 py-2 rounded-xl bg-gray-800/40 hover:bg-gray-800/60 border border-gray-700/30 text-gray-400 hover:text-white text-xs transition-all"
            >
              <Settings size={12} />
              <span>إعداد مزود الذكاء</span>
              <span className="ml-auto">→</span>
            </button>
            <div className="flex items-center gap-2 text-xs">
              {llmStatus?.gemini_configured ? (
                <span className="flex items-center gap-1 text-emerald-400">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
                  Gemini
                </span>
              ) : null}
              {llmStatus?.huggingface_configured ? (
                <span className="flex items-center gap-1 text-yellow-400">
                  <span className="w-1.5 h-1.5 rounded-full bg-yellow-400" />
                  HF
                </span>
              ) : null}
              {!llmStatus?.gemini_configured && !llmStatus?.huggingface_configured ? (
                <span className="flex items-center gap-1 text-gray-500">
                  <span className="w-1.5 h-1.5 rounded-full bg-gray-500" />
                  وضع العرض
                </span>
              ) : (
                <span className="text-gray-500 ml-auto">متصل</span>
              )}
            </div>
          </div>
        </div>
      </div>
    </>
  )
}

// Suggested prompts
const SUGGESTIONS = [
  { icon: Search, text: "ابحث عن آخر تطورات الذكاء الاصطناعي 2026", color: "text-cyan-400" },
  { icon: Code, text: "Write a Python script to analyze data", color: "text-emerald-400" },
  { icon: FileText, text: "أنشئ خطة مشروع كاملة", color: "text-violet-400" },
  { icon: Terminal, text: "Check system info and disk usage", color: "text-orange-400" },
]

function App() {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [activeConvId, setActiveConvId] = useState<string>()
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [tools, setTools] = useState<any[]>([])
  const [showConfigModal, setShowConfigModal] = useState(false)
  const [llmStatus, setLlmStatus] = useState<any>(null)
  const [apiAvailable, setApiAvailable] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  // Scroll to bottom
  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [])

  useEffect(() => {
    scrollToBottom()
  }, [messages, scrollToBottom])

  // Load initial data
  useEffect(() => {
    loadConversations()
    loadTools()
    loadLLMStatus()
  }, [])

  async function loadConversations() {
    try {
      const data = await apiGet('/api/conversations')
      setConversations(data.conversations || [])
      setApiAvailable(true)
    } catch {
      console.log('API not available, running in demo mode')
      setApiAvailable(false)
    }
  }

  async function loadTools() {
    try {
      const data = await apiGet('/api/tools')
      setTools(data.tools || [])
    } catch {
      setTools([
        { name: 'web_search', description: 'Search the web for information', category: 'research' },
        { name: 'execute_code', description: 'Execute Python/JS/Bash code', category: 'execution' },
        { name: 'file_manager', description: 'Manage workspace files', category: 'file_management' },
        { name: 'shell', description: 'Execute shell commands', category: 'execution' },
        { name: 'think', description: 'Internal reasoning and planning', category: 'reasoning' },
      ])
    }
  }

  async function loadLLMStatus() {
    try {
      const data = await apiGet('/api/llm/status')
      setLlmStatus(data)
    } catch {
      setLlmStatus(null)
    }
  }

  async function configureLLM(config: any) {
    try {
      const data = await apiPost('/api/llm/configure', config)
      setLlmStatus(data.providers)
      // Show success notification
      const successMsg: Message = {
        id: `msg_${Date.now()}`,
        role: 'assistant',
        content: `✅ تم تكوين مزود الذكاء بنجاح!\n\n${
          data.providers?.gemini_configured ? '🔷 Gemini API: مُفعّل\n' : ''
        }${
          data.providers?.huggingface_configured ? '🤗 HuggingFace: مُفعّل\n' : ''
        }\nالمزود الأساسي: ${data.providers?.primary || 'gemini'}`,
        timestamp: new Date().toISOString(),
      }
      setMessages(prev => [...prev, successMsg])
    } catch (error) {
      console.error('Failed to configure LLM:', error)
    }
  }

  async function sendMessage(content?: string) {
    const messageText = content || input.trim()
    if (!messageText || isLoading) return

    setInput('')
    setIsLoading(true)

    // Add user message
    const userMsg: Message = {
      id: `msg_${Date.now()}`,
      role: 'user',
      content: messageText,
      timestamp: new Date().toISOString(),
    }
    setMessages(prev => [...prev, userMsg])

    // Add streaming assistant message
    const assistantMsg: Message = {
      id: `msg_${Date.now() + 1}`,
      role: 'assistant',
      content: '',
      timestamp: new Date().toISOString(),
      isStreaming: true,
    }
    setMessages(prev => [...prev, assistantMsg])

    try {
      const data = await apiPost('/api/chat', {
        message: messageText,
        conversation_id: activeConvId,
      })

      // Update assistant message with response
      setMessages(prev => prev.map(m =>
        m.id === assistantMsg.id
          ? {
              ...m,
              content: data.response,
              steps: data.steps || [],
              tool_calls: data.tool_calls || [],
              isStreaming: false,
            }
          : m
      ))

      if (data.conversation_id && !activeConvId) {
        setActiveConvId(data.conversation_id)
        loadConversations()
      }
    } catch (error) {
      // Demo mode response
      const demoResponse = generateDemoResponse(messageText)
      setMessages(prev => prev.map(m =>
        m.id === assistantMsg.id
          ? { ...m, content: demoResponse.content, steps: demoResponse.steps, isStreaming: false }
          : m
      ))
    } finally {
      setIsLoading(false)
    }
  }

  function generateDemoResponse(input: string) {
    const lower = input.toLowerCase()
    const steps: Step[] = []

    if (lower.includes('search') || lower.includes('find') || lower.includes('research') || lower.includes('ابحث')) {
      steps.push({
        id: 'step_1', description: 'تحليل طلب البحث',
        status: 'completed',
        tool_calls: [{ id: 'tc_1', name: 'think', arguments: { thought: 'Breaking down the query' }, status: 'completed' }]
      })
      steps.push({
        id: 'step_2', description: 'البحث على الويب',
        status: 'completed',
        tool_calls: [{ id: 'tc_2', name: 'web_search', arguments: { query: input }, status: 'completed' }]
      })
      return {
        content: `🔍 **نتائج البحث**\n\nتم تحليل طلبك: "${input}"\n\n📊 **النقاط الرئيسية:**\n1. توجد تطورات مهمة في هذا المجال\n2. مصادر متعددة تؤكد أهمية هذا الموضوع\n3. إنجازات حديثة فتحت إمكانيات جديدة\n\n💡 **ملاحظة:** للحصول على نتائج بحث حقيقية، قم بتكوين Gemini API أو HuggingFace Token من الإعدادات.`,
        steps
      }
    } else if (lower.includes('code') || lower.includes('script') || lower.includes('program') || lower.includes('كود')) {
      steps.push({
        id: 'step_1', description: 'تحليل متطلبات الكود',
        status: 'completed',
        tool_calls: [{ id: 'tc_1', name: 'think', arguments: { thought: 'Planning code structure' }, status: 'completed' }]
      })
      steps.push({
        id: 'step_2', description: 'كتابة وتنفيذ الكود',
        status: 'completed',
        tool_calls: [{ id: 'tc_2', name: 'execute_code', arguments: { code: 'print("Hello World")' }, status: 'completed' }]
      })
      return {
        content: `💻 **تم إنشاء الكود بنجاح**\n\n\`\`\`python\ndef analyze_data(data):\n    """تحليل البيانات وإحصائياتها"""\n    results = {\n        "total": len(data),\n        "mean": sum(data) / len(data),\n        "min": min(data),\n        "max": max(data),\n    }\n    return results\n\`\`\`\n\n✅ تم التحقق من الكود. في وضع الإنتاج مع API مُفعّل، سأقوم بتنفيذ الكود فعلاً وعرض النتائج.`,
        steps
      }
    } else {
      steps.push({
        id: 'step_1', description: 'فهم الطلب',
        status: 'completed',
        tool_calls: [{ id: 'tc_1', name: 'think', arguments: { thought: input }, status: 'completed' }]
      })
      return {
        content: `🧠 **تم تحليل طلبك**\n\n"${input}"\n\n📋 **الخطوات المتبعة:**\n1. ✅ تحليل الطلب وتحديد المكونات الأساسية\n2. ✅ وضع خطة التنفيذ\n3. ✅ معالجة الطلب\n\n🔧 **للحصول على ردود ذكية حقيقية:**\n- افتح الإعدادات من الشريط الجانبي\n- أضف Gemini API Key (مجاني من Google)\n- أو أضف HuggingFace Token (مجاني)\n\n🌐 **الأدوات المتاحة:**\n- 🔍 بحث ويب\n- 💻 تنفيذ كود\n- 📁 إدارة ملفات\n- 🖥️ أوامر Shell\n- 🧠 تفكير عميق`,
        steps
      }
    }
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  function handleNewConversation() {
    setMessages([])
    setActiveConvId(undefined)
  }

  const showSuggestions = messages.length === 0

  return (
    <div className="h-screen flex bg-[#0a0a1a] text-white overflow-hidden">
      {/* LLM Config Modal (lazy-loaded with Suspense) */}
      <Suspense fallback={null}>
        <LLMConfigModal
          isOpen={showConfigModal}
          onClose={() => setShowConfigModal(false)}
          onConfigure={configureLLM}
          currentStatus={llmStatus}
        />
      </Suspense>

      {/* Sidebar */}
      <Sidebar
        conversations={conversations}
        activeId={activeConvId}
        onSelect={(id) => setActiveConvId(id)}
        onNew={handleNewConversation}
        onDelete={(id) => setConversations(prev => prev.filter(c => c.id !== id))}
        isOpen={sidebarOpen}
        onToggle={() => setSidebarOpen(!sidebarOpen)}
        llmStatus={llmStatus}
        onOpenConfig={() => setShowConfigModal(true)}
      />

      {/* Main content */}
      <div className={`flex-1 flex flex-col transition-all duration-300 ${sidebarOpen ? 'ml-72' : 'ml-0'}`}>
        {/* Header */}
        <header className="flex items-center justify-between px-6 py-3 border-b border-gray-800/50 bg-[#0d0d1a]/80 backdrop-blur-xl">
          <div className="flex items-center gap-3 pl-10">
            <div className={`w-2 h-2 rounded-full ${apiAvailable ? (llmStatus?.gemini_configured || llmStatus?.huggingface_configured ? 'bg-emerald-400' : 'bg-yellow-400') : 'bg-red-400'} animate-pulse`} />
            <h2 className="text-sm font-medium text-gray-300">celia.pro Agent</h2>
            {!apiAvailable && (
              <span className="text-xs px-2 py-0.5 rounded-full bg-red-500/10 text-red-400">
                Demo Mode
              </span>
            )}
            {llmStatus?.primary && (
              <span className="text-xs px-2 py-0.5 rounded-full bg-gray-800/60 text-gray-500">
                {llmStatus.primary === 'gemini' ? '🔷 Gemini' : '🤗 HuggingFace'}
              </span>
            )}
          </div>
          <div className="flex items-center gap-2">
            {tools.map(tool => {
              const Icon = toolIcons[tool.name] || Zap
              return (
                <div key={tool.name} className="group relative">
                  <div className="p-2 rounded-lg bg-gray-800/40 text-gray-500 hover:text-cyan-400 transition-colors cursor-help">
                    <Icon size={14} />
                  </div>
                  <div className="absolute bottom-full right-0 mb-2 px-2 py-1 bg-gray-800 rounded-md text-xs text-gray-300 whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none">
                    {tool.name}
                  </div>
                </div>
              )
            })}
          </div>
        </header>

        {/* Messages area */}
        <div className="flex-1 overflow-y-auto">
          {showSuggestions ? (
            <div className="h-full flex flex-col items-center justify-center px-6">
              {/* Hero */}
              <div className="text-center mb-10">
                <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-cyan-500 to-blue-600 flex items-center justify-center mx-auto mb-4 shadow-lg shadow-cyan-500/20">
                  <Sparkles size={28} className="text-white" />
                </div>
                <h1 className="text-3xl font-bold bg-gradient-to-r from-cyan-400 to-blue-400 bg-clip-text text-transparent mb-2">
                  celia.pro
                </h1>
                <p className="text-gray-500 text-sm max-w-md">
                  نظام وكيل ذكاء اصطناعي متقدم متعدد الأدوات.
                  يبحث، يكتب كود، يدير ملفات، وينفذ المهام بذكاء.
                </p>
                <div className="flex items-center justify-center gap-4 mt-4">
                  <span className="text-xs px-2 py-1 rounded-lg bg-blue-500/10 text-blue-400 border border-blue-500/20">
                    🔷 Gemini Free
                  </span>
                  <span className="text-xs px-2 py-1 rounded-lg bg-yellow-500/10 text-yellow-400 border border-yellow-500/20">
                    🤗 HuggingFace Free
                  </span>
                </div>
              </div>

              {/* Suggestions */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3 max-w-2xl w-full">
                {SUGGESTIONS.map((suggestion, i) => (
                  <button
                    key={i}
                    onClick={() => sendMessage(suggestion.text)}
                    className="flex items-center gap-3 p-4 rounded-xl bg-gray-800/30 hover:bg-gray-800/60 border border-gray-700/30 hover:border-gray-600/50 text-left transition-all group"
                  >
                    <suggestion.icon size={18} className={`${suggestion.color} flex-shrink-0`} />
                    <span className="text-sm text-gray-400 group-hover:text-gray-200 transition-colors">
                      {suggestion.text}
                    </span>
                  </button>
                ))}
              </div>

              {/* Quick Config */}
              <button
                onClick={() => setShowConfigModal(true)}
                className="mt-8 flex items-center gap-2 px-4 py-2.5 rounded-xl bg-gradient-to-r from-cyan-500/10 to-blue-500/10 hover:from-cyan-500/20 hover:to-blue-500/20 border border-cyan-500/20 text-cyan-400 text-sm transition-all"
              >
                <Settings size={14} />
                <span>إعداد API Keys للبدء</span>
              </button>

              {/* Capabilities */}
              <div className="mt-6 flex flex-wrap justify-center gap-4">
                {[
                  { icon: Globe, label: 'Web Search' },
                  { icon: Code, label: 'Code Execution' },
                  { icon: FileText, label: 'File Management' },
                  { icon: Terminal, label: 'Shell Commands' },
                  { icon: Brain, label: 'Deep Reasoning' },
                ].map(cap => (
                  <div key={cap.label} className="flex items-center gap-1.5 text-xs text-gray-600">
                    <cap.icon size={12} />
                    <span>{cap.label}</span>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <div className="max-w-4xl mx-auto py-4">
              {messages.map(msg => (
                <MessageBubble key={msg.id} message={msg} />
              ))}
              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        {/* Input area */}
        <div className="border-t border-gray-800/50 bg-[#0d0d1a]/80 backdrop-blur-xl p-4">
          <div className="max-w-4xl mx-auto">
            <div className="relative flex items-end gap-3 bg-gray-800/40 rounded-2xl border border-gray-700/50 focus-within:border-cyan-500/30 transition-colors">
              <textarea
                ref={textareaRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="اسأل celia.pro أي شيء..."
                rows={1}
                className="flex-1 bg-transparent px-4 py-3.5 text-sm text-white placeholder-gray-500 resize-none outline-none max-h-32"
                style={{ minHeight: '44px' }}
              />
              <button
                onClick={() => sendMessage()}
                disabled={!input.trim() || isLoading}
                className="m-2 p-2.5 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-500 hover:from-cyan-400 hover:to-blue-400 disabled:from-gray-700 disabled:to-gray-700 disabled:text-gray-500 text-white transition-all disabled:cursor-not-allowed"
              >
                {isLoading ? <Loader2 size={16} className="animate-spin" /> : <Send size={16} />}
              </button>
            </div>
            <p className="text-center text-xs text-gray-600 mt-2">
              celia.pro مدعوم بـ Gemini & HuggingFace | قد يُنتج أخطاء. تحقق من المعلومات المهمة.
            </p>
            <p className="text-center text-xs text-gray-700 mt-1">
              © 2026 celia.pro — جميع الحقوق محفوظة | محمي بترخيص خاص صارم
            </p>
            <p className="text-center text-xs text-red-500/70 mt-1">
              ⚠️ أي استخدام دون إذن صريح ممنوع تماماً
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}

export default App
