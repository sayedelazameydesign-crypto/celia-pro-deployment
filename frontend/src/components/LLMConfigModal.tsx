/**
 * LLM Configuration Modal (Lazy-loaded)
 * 
 * Extracted from App.tsx for code splitting.
 * This modal is only loaded when the user clicks "Configure LLM".
 * Reduces main bundle size by ~4KB.
 */

import { useState, useEffect } from 'react'
import { Key, Cpu, CheckCircle2 } from 'lucide-react'

interface Provider {
  id: string
  name: string
  description: string
  models: string[]
  requires: string
  link: string
}

// API helper (shared pattern with App.tsx)
async function apiGet(endpoint: string) {
  const token = localStorage.getItem('auth_token')
  const headers: Record<string, string> = {}
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }
  const res = await fetch(`${endpoint}`, { headers })
  if (!res.ok) throw new Error(`API Error: ${res.statusText}`)
  return res.json()
}

interface LLMConfigModalProps {
  isOpen: boolean
  onClose: () => void
  onConfigure: (config: any) => void
  currentStatus: any
}

export default function LLMConfigModal({ isOpen, onClose, onConfigure, currentStatus }: LLMConfigModalProps) {
  const [geminiKey, setGeminiKey] = useState('')
  const [hfToken, setHfToken] = useState('')
  const [primary, setPrimary] = useState<'gemini' | 'huggingface'>('gemini')
  const [geminiModel, setGeminiModel] = useState('gemini-2.0-flash')
  const [hfModel, setHfModel] = useState('meta-llama/Llama-3.3-70B-Instruct')
  const [providers, setProviders] = useState<Provider[]>([])

  useEffect(() => {
    if (isOpen) {
      apiGet('/api/llm/providers').then(data => setProviders(data.providers || [])).catch(() => {})
    }
  }, [isOpen])

  if (!isOpen) return null

  const handleSubmit = () => {
    onConfigure({
      gemini_api_key: geminiKey || undefined,
      hf_token: hfToken || undefined,
      primary_provider: primary,
      gemini_model: geminiModel,
      hf_model: hfModel,
    })
    onClose()
  }

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4">
      <div className="bg-[#0d0d1a] border border-gray-700/50 rounded-2xl w-full max-w-lg max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="p-6 border-b border-gray-800/50">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-cyan-500/20 to-blue-500/20 flex items-center justify-center">
                <Cpu size={20} className="text-cyan-400" />
              </div>
              <div>
                <h2 className="text-lg font-bold text-white">إعداد مزود الذكاء</h2>
                <p className="text-xs text-gray-500">Gemini API & HuggingFace (الخطة المجانية)</p>
              </div>
            </div>
            <button onClick={onClose} className="text-gray-500 hover:text-white p-2">✕</button>
          </div>
        </div>

        {/* Status */}
        {currentStatus && (
          <div className="mx-6 mt-4 p-3 rounded-xl bg-gray-800/40 border border-gray-700/30">
            <div className="flex items-center gap-2 text-xs">
              {currentStatus.gemini_configured ? (
                <span className="text-emerald-400 flex items-center gap-1"><CheckCircle2 size={12} /> Gemini مُفعّل</span>
              ) : (
                <span className="text-gray-500">Gemini غير مُفعّل</span>
              )}
              <span className="text-gray-700">|</span>
              {currentStatus.huggingface_configured ? (
                <span className="text-emerald-400 flex items-center gap-1"><CheckCircle2 size={12} /> HuggingFace مُفعّل</span>
              ) : (
                <span className="text-gray-500">HuggingFace غير مُفعّل</span>
              )}
            </div>
          </div>
        )}

        {/* Content */}
        <div className="p-6 space-y-5">
          {/* Provider Selection */}
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-2">المزود الأساسي</label>
            <div className="grid grid-cols-2 gap-3">
              <button
                onClick={() => setPrimary('gemini')}
                className={`p-3 rounded-xl border text-left transition-all ${
                  primary === 'gemini'
                    ? 'border-cyan-500/50 bg-cyan-500/10'
                    : 'border-gray-700/50 bg-gray-800/30 hover:border-gray-600'
                }`}
              >
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-lg">🔷</span>
                  <span className="text-sm font-medium text-white">Gemini</span>
                </div>
                <p className="text-xs text-gray-500">Google - مجاني</p>
              </button>
              <button
                onClick={() => setPrimary('huggingface')}
                className={`p-3 rounded-xl border text-left transition-all ${
                  primary === 'huggingface'
                    ? 'border-yellow-500/50 bg-yellow-500/10'
                    : 'border-gray-700/50 bg-gray-800/30 hover:border-gray-600'
                }`}
              >
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-lg">🤗</span>
                  <span className="text-sm font-medium text-white">HuggingFace</span>
                </div>
                <p className="text-xs text-gray-500">مفتوح المصدر - مجاني</p>
              </button>
            </div>
          </div>

          {/* Gemini Key */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="block text-sm font-medium text-gray-300">
                🔷 Gemini API Key
              </label>
              <a
                href="https://aistudio.google.com/app/apikey"
                target="_blank"
                rel="noopener noreferrer"
                className="text-xs text-cyan-400 hover:text-cyan-300"
              >
                احصل على مفتاح مجاني ←
              </a>
            </div>
            <div className="relative">
              <Key size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500" />
              <input
                type="password"
                value={geminiKey}
                onChange={(e) => setGeminiKey(e.target.value)}
                placeholder="AIza..."
                className="w-full bg-gray-800/50 border border-gray-700/50 rounded-xl pl-9 pr-4 py-2.5 text-sm text-white placeholder-gray-600 focus:border-cyan-500/50 focus:outline-none"
              />
            </div>
            {primary === 'gemini' && (
              <select
                value={geminiModel}
                onChange={(e) => setGeminiModel(e.target.value)}
                className="mt-2 w-full bg-gray-800/50 border border-gray-700/50 rounded-xl px-3 py-2 text-sm text-gray-300 focus:outline-none"
              >
                <option value="gemini-2.0-flash">Gemini 2.0 Flash (أسرع)</option>
                <option value="gemini-2.0-flash-lite">Gemini 2.0 Flash Lite</option>
                <option value="gemini-1.5-flash">Gemini 1.5 Flash</option>
                <option value="gemini-1.5-flash-8b">Gemini 1.5 Flash 8B</option>
              </select>
            )}
          </div>

          {/* HuggingFace Token */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="block text-sm font-medium text-gray-300">
                🤗 HuggingFace Token
              </label>
              <a
                href="https://huggingface.co/settings/tokens"
                target="_blank"
                rel="noopener noreferrer"
                className="text-xs text-yellow-400 hover:text-yellow-300"
              >
                احصل على Token مجاني ←
              </a>
            </div>
            <div className="relative">
              <Key size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500" />
              <input
                type="password"
                value={hfToken}
                onChange={(e) => setHfToken(e.target.value)}
                placeholder="hf_..."
                className="w-full bg-gray-800/50 border border-gray-700/50 rounded-xl pl-9 pr-4 py-2.5 text-sm text-white placeholder-gray-600 focus:border-yellow-500/50 focus:outline-none"
              />
            </div>
            {primary === 'huggingface' && (
              <select
                value={hfModel}
                onChange={(e) => setHfModel(e.target.value)}
                className="mt-2 w-full bg-gray-800/50 border border-gray-700/50 rounded-xl px-3 py-2 text-sm text-gray-300 focus:outline-none"
              >
                <option value="meta-llama/Llama-3.3-70B-Instruct">Llama 3.3 70B (الأقوى)</option>
                <option value="mistralai/Mistral-7B-Instruct-v0.3">Mistral 7B</option>
                <option value="google/gemma-2-2b-it">Gemma 2 2B</option>
                <option value="HuggingFaceH4/zephyr-7b-beta">Zephyr 7B</option>
              </select>
            )}
          </div>

          {/* Info */}
          <div className="p-3 rounded-xl bg-blue-500/5 border border-blue-500/20">
            <p className="text-xs text-blue-300/80 leading-relaxed">
              💡 <strong>الخطة المجانية:</strong> Gemini يسمح بـ 15 طلب/دقيقة و1M token/دقيقة.
              HuggingFace يوفر وصول مجاني للنماذج المفتوحة مع حدود استخدام.
              يمكنك تفعيل كلا المزودين وسيتم التبديل تلقائياً عند فشل أحدهما.
            </p>
            {providers.length > 0 && (
              <p className="text-xs text-gray-500 mt-2">
                {providers.length} مزودين متاحين
              </p>
            )}
          </div>
        </div>

        {/* Footer */}
        <div className="p-6 border-t border-gray-800/50 flex gap-3">
          <button
            onClick={onClose}
            className="flex-1 px-4 py-2.5 rounded-xl border border-gray-700/50 text-gray-400 hover:text-white hover:border-gray-600 text-sm font-medium transition-all"
          >
            إلغاء
          </button>
          <button
            onClick={handleSubmit}
            className="flex-1 px-4 py-2.5 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-500 hover:from-cyan-400 hover:to-blue-400 text-white text-sm font-medium transition-all"
          >
            حفظ وتفعيل
          </button>
        </div>
      </div>
    </div>
  )
}
