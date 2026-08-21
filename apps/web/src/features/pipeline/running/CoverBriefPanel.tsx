import type { ReactNode } from "react"
import {
  Image,
  ImageOff,
  Lock,
  Palette,
  ShieldCheck,
} from "lucide-react"
import type { CoverArtifact } from "../contracts/delivery"

export function CoverBriefPanel({ artifact }: { artifact: CoverArtifact }) {
  return (
    <section className="min-w-0 space-y-5">
      <div className="border-y border-hairline py-4">
        <SectionHeading icon={<ShieldCheck size={13} />} title="核心概念" />
        <p className="font-serif text-sm text-ink leading-7 mt-3">
          {artifact.brief.concept}
        </p>
      </div>

      <div>
        <SectionHeading icon={<Image size={13} />} title="画面指令" />
        <p className="text-xs text-ash leading-6 mt-3 whitespace-pre-wrap">
          {artifact.brief.image_prompt}
        </p>
      </div>

      <div>
        <SectionHeading icon={<Palette size={13} />} title="色彩基调" />
        <div className="flex flex-wrap gap-2 mt-3">
          {artifact.brief.palette.map((color) => (
            <div
              key={color}
              className="flex items-center gap-2 border border-hairline rounded px-2 py-1.5 bg-surface"
            >
              <span
                className="w-5 h-5 rounded-sm border border-white/10"
                style={{ backgroundColor: color }}
              />
              <code className="text-[10px] text-fog">{color}</code>
            </div>
          ))}
        </div>
      </div>

      <div>
        <SectionHeading icon={<ImageOff size={13} />} title="画面排除项" />
        <div className="flex flex-wrap gap-1.5 mt-3">
          {artifact.brief.negative_constraints.length ? (
            artifact.brief.negative_constraints.map((item) => (
              <span key={item} className="badge badge-ash">
                {item}
              </span>
            ))
          ) : (
            <span className="text-xs text-fog">未设置额外排除项</span>
          )}
        </div>
      </div>

      <div className="banner-action">
        <Lock size={13} />
        <span>
          视觉 Brief 不能直接编辑；如需改变构图或风格，请使用定向换稿生成新候选。
        </span>
      </div>
    </section>
  )
}

function SectionHeading({ icon, title }: { icon: ReactNode; title: string }) {
  return (
    <div className="flex items-center gap-2 text-xs text-ash">
      {icon}
      <span>{title}</span>
    </div>
  )
}
