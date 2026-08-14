import { useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import type { ProjectRecord, ProjectSummary } from '../../contracts';
import { useUICommandContext, useWorkflowConfigContext } from '../../state/pipelineShellContext';
import { useStudioProjects } from '../../state/useStudioProjects';
import { RevealText } from '../RevealText';
import { NewProjectWizard } from './NewProjectWizard';
import { ProjectBookshelf } from './ProjectBookshelf';
import { StudioMobileNav } from './StudioMobileNav';
import { TemplateManagerSection } from './TemplateManagerSection';

/** Studio Shell main area: project card wall, new-project wizard, and template management. */
export function StudioWorkbench() {
  const ui = useUICommandContext();
  const { qualityMode } = useWorkflowConfigContext();
  const studio = useStudioProjects(true);
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const wizardOpen = searchParams.get('new') === '1';
  const templateView = searchParams.get('view') === 'templates';
  const initialTemplateId = searchParams.get('template') ?? '';
  const [openingProjectId, setOpeningProjectId] = useState('');
  const [openError, setOpenError] = useState('');

  const studioViewRoute = templateView ? '/studio?view=templates' : '/studio';
  const openWizard = () => navigate(`${studioViewRoute}${templateView ? '&' : '?'}new=1`, { replace: false });
  const closeWizard = () => navigate(studioViewRoute, { replace: true });

  const openProject = async (project: ProjectRecord, summary: ProjectSummary | null) => {
    if (openingProjectId) return;
    setOpeningProjectId(project.id);
    setOpenError('');
    try {
      const opened = await ui.openProject(project, summary?.latest_run ?? null);
      if (!opened) setOpenError(`未能打开「${project.title}」，请检查项目数据后重试。`);
    } catch (error) {
      setOpenError(error instanceof Error ? `打开作品失败：${error.message}` : '打开作品失败，请稍后重试。');
    } finally {
      setOpeningProjectId('');
    }
  };

  return (
    <div className="studio-workbench" data-testid="studio-workbench">
      <StudioMobileNav />
      {openError ? <div className="studio-open-toast" role="alert"><span>{openError}</span><button onClick={() => setOpenError('')} type="button">关闭</button></div> : null}
      {templateView ? (
        <TemplateManagerSection
          error={studio.templateError}
          onDelete={studio.removeTemplate}
          onDuplicate={studio.duplicateTemplate}
          onRename={studio.renameTemplate}
          onUse={(templateId) => navigate(`/studio?view=templates&new=1&template=${encodeURIComponent(templateId)}`, { replace: false })}
          templates={studio.templates}
        />
      ) : (
        <>
          <section aria-labelledby="studio-projects-heading" className="studio-projects nw-reveal" id="studio-projects">
            <div className="studio-section-head">
              <RevealText as="h1" className="studio-section-title" id="studio-projects-heading" text="作品库" />
              <p>{studio.loading ? '正在同步作品状态…' : `共 ${studio.projects.length} 部作品`}</p>
            </div>
            <ProjectBookshelf
              error={studio.error}
              loading={studio.loading}
              onCreate={openWizard}
              onOpen={openProject}
              openingProjectId={openingProjectId}
              projects={studio.projects}
              summaries={studio.summaries}
            />
          </section>
        </>
      )}
      <NewProjectWizard
        initialTemplateId={initialTemplateId}
        onClose={closeWizard}
        onCreate={studio.create}
        onCreated={(project) => {
          void openProject(project, null);
        }}
        open={wizardOpen}
        qualityMode={qualityMode}
        templates={studio.templates}
      />
    </div>
  );
}
