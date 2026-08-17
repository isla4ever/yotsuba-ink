import { useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import type { ProjectRecord, ProjectSummary } from '../../contracts';
import { useUICommandContext, useWorkflowConfigContext } from '../../state/pipelineShellContext';
import { useStudioProjects } from '../../state/useStudioProjects';
import { NewProjectWizard } from './NewProjectWizard';
import { ProjectBookshelf } from './ProjectBookshelf';
import { StudioLibraryOverview } from './StudioLibraryOverview';
import { StudioMobileNav } from './StudioMobileNav';
import { TemplateManagerSection } from './TemplateManagerSection';
import { studioWorkflowRoute } from '../../lib/stageRoutes';

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
            <StudioLibraryOverview loading={studio.loading} onCreate={openWizard} projects={studio.projects} summaries={studio.summaries} />
            <ProjectBookshelf
              error={studio.error}
              loading={studio.loading}
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
        onConfigure={async (templateId) => {
          const draft = await studio.createOneTimeWorkflow(templateId);
          navigate(studioWorkflowRoute(draft.id), { replace: false });
        }}
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
