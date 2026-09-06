import { useState } from "react"
import {
  Bot,
  MessagesSquare,
  MonitorCog,
  Moon,
  Settings as SettingsIcon,
  Sun,
} from "lucide-react"
import { useApp } from "../state/PipelineAppProvider"
import { ProviderSettingsPanel } from "@/features/pipeline/settings/ProviderSettingsPanel"
import { AuthorCollaborationSettings } from "@/features/pipeline/settings/AuthorCollaborationSettings"

type SettingsSection = "providers" | "collaboration" | "interface"

export default function SettingsPage() {
  const { theme, toggleTheme } = useApp()
  const [activeSection, setActiveSection] =
    useState<SettingsSection>("providers")
  const sections = [
    { id: "providers" as const, label: "AI 服务", icon: <Bot size={13} /> },
    {
      id: "collaboration" as const,
      label: "作者协作",
      icon: <MessagesSquare size={13} />,
    },
    { id: "interface" as const, label: "界面", icon: <MonitorCog size={13} /> },
  ]

  return (
    <div className="settings-screen">
      <aside className="settings-section-nav">
        <header>
          <SettingsIcon size={14} />
          <span>设置</span>
        </header>
        <nav>
          {sections.map((section) => (
            <button
              key={section.id}
              type="button"
              className={activeSection === section.id ? "active" : ""}
              onClick={() => setActiveSection(section.id)}
            >
              {section.icon}
              <span>{section.label}</span>
            </button>
          ))}
        </nav>
      </aside>

      <main className="settings-content">
        {activeSection === "providers" ? (
          <ProviderSettingsPanel />
        ) : activeSection === "collaboration" ? (
          <AuthorCollaborationSettings />
        ) : (
          <div className="settings-interface-panel">
            <header>
              <span>界面</span>
              <h1>显示偏好</h1>
            </header>
            <section>
              <div>
                <strong>主题</strong>
                <small>{theme === "dark" ? "深色界面" : "浅色界面"}</small>
              </div>
              <button
                type="button"
                className="btn btn-secondary"
                onClick={toggleTheme}
              >
                {theme === "dark" ? <Sun size={14} /> : <Moon size={14} />}
                切换为{theme === "dark" ? "浅色" : "深色"}
              </button>
            </section>
          </div>
        )}
      </main>
    </div>
  )
}
