import type { Config } from 'tailwindcss'

export default {
  content: ['./index.html', './src/**/*.{vue,ts,tsx}'],
  darkMode: 'class', // 通过 documentElement.classList.toggle('dark') 控制
  theme: {
    extend: {
      fontFamily: {
        sans: [
          'MiSans',
          '-apple-system',
          'BlinkMacSystemFont',
          '"PingFang SC"',
          '"HarmonyOS Sans SC"',
          'system-ui',
          'sans-serif',
        ],
        mono: ['"JetBrains Mono"', 'Menlo', 'Consolas', 'monospace'],
      },
      colors: {
        // 中性面 — 从 tokens.css var() 注入,保留 alpha 工具(/60 等)
        bg: {
          base: 'rgb(var(--bg-base-rgb) / <alpha-value>)',
          surface: 'rgb(var(--bg-surface-rgb) / <alpha-value>)',
          subtle: 'rgb(var(--bg-subtle-rgb) / <alpha-value>)',
          inset: 'rgb(var(--bg-inset-rgb) / <alpha-value>)',
        },
        // 文字
        ink: {
          1: 'rgb(var(--ink-1-rgb) / <alpha-value>)',
          2: 'rgb(var(--ink-2-rgb) / <alpha-value>)',
          3: 'rgb(var(--ink-3-rgb) / <alpha-value>)',
          4: 'rgb(var(--ink-4-rgb) / <alpha-value>)',
          5: 'rgb(var(--ink-5-rgb) / <alpha-value>)',
        },
        // 边线
        line: {
          DEFAULT: 'rgb(var(--line-rgb) / <alpha-value>)',
          subtle: 'rgb(var(--line-subtle-rgb) / <alpha-value>)',
          strong: 'rgb(var(--line-strong-rgb) / <alpha-value>)',
        },
        // 主调 Accent
        accent: {
          DEFAULT: 'rgb(var(--accent-rgb) / <alpha-value>)',
          hover: 'rgb(var(--accent-hover-rgb) / <alpha-value>)',
          soft: 'rgb(var(--accent-soft-rgb) / <alpha-value>)',
        },
        // 模块 Hue — Vision Pro 多色
        hue: {
          chat: 'rgb(var(--hue-chat-rgb) / <alpha-value>)',
          ppt: 'rgb(var(--hue-ppt-rgb) / <alpha-value>)',
          library: 'rgb(var(--hue-library-rgb) / <alpha-value>)',
          memory: 'rgb(var(--hue-memory-rgb) / <alpha-value>)',
          settings: 'rgb(var(--hue-settings-rgb) / <alpha-value>)',
          dashboard: 'rgb(var(--hue-dashboard-rgb) / <alpha-value>)',
        },
        // 语义
        success: 'rgb(var(--success-rgb) / <alpha-value>)',
        warning: 'rgb(var(--warning-rgb) / <alpha-value>)',
        danger: 'rgb(var(--danger-rgb) / <alpha-value>)',
        info: 'rgb(var(--info-rgb) / <alpha-value>)',
        // 兼容旧代码(原 brand 类)— 别名指向 accent
        brand: {
          DEFAULT: 'rgb(var(--accent-rgb) / <alpha-value>)',
          hover: 'rgb(var(--accent-hover-rgb) / <alpha-value>)',
          subtle: 'rgb(var(--accent-soft-rgb) / <alpha-value>)',
        },
      },
      boxShadow: {
        card: 'var(--shadow-card)',
        'card-hover': 'var(--shadow-card-hover)',
        pop: 'var(--shadow-pop)',
        elevated: 'var(--shadow-elevated)',
      },
      borderRadius: {
        control: 'var(--radius-control)',
        card: 'var(--radius-card)',
        'card-lg': 'var(--radius-card-lg)',
        bubble: 'var(--radius-bubble)',
        pill: 'var(--radius-pill)',
      },
      transitionTimingFunction: {
        spring: 'cubic-bezier(0.2, 0.8, 0.2, 1)',
        'apple-out': 'cubic-bezier(0.16, 1, 0.3, 1)',
      },
      transitionDuration: {
        DEFAULT: '220ms',
        quick: '120ms',
        base: '220ms',
        slow: '380ms',
      },
      keyframes: {
        'slide-up-fade': {
          '0%': { opacity: '0', transform: 'translateY(8px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        'fade-in': {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        'pulse-soft': {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.6' },
        },
      },
      animation: {
        'slide-up-fade': 'slide-up-fade 220ms cubic-bezier(0.2, 0.8, 0.2, 1)',
        'fade-in': 'fade-in 180ms ease-out',
        'pulse-soft': 'pulse-soft 1.6s ease-in-out infinite',
      },
    },
  },
  plugins: [],
} satisfies Config
