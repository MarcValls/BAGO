// @vitest-environment happy-dom
import { describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom';
import { fireEvent, render, waitFor } from '@testing-library/react';
import { PipelineGuidedBuilder } from '../src/features/pipeline/PipelineGuidedBuilder';

describe('PipelineGuidedBuilder quick creation', () => {
  const objective = 'Revisar README de la demo';

  function renderBuilder(onCreatePlan = vi.fn().mockResolvedValue(undefined)) {
    return {
      onCreatePlan,
      ...render(<PipelineGuidedBuilder
        client={{} as never}
        task={objective}
        hasSteps={false}
        onTaskChange={vi.fn()}
        onCreatePlan={onCreatePlan}
        onOpenCapabilities={vi.fn()}
        onCreated={vi.fn()}
      />)
    };
  }

  it('keeps the supplied objective and limits the basic path to objective and review', () => {
    const { getByDisplayValue, getByLabelText, queryByRole } = renderBuilder();

    expect(getByDisplayValue(objective)).toBeInTheDocument();
    expect(getByLabelText('Pasos del creador')).toHaveTextContent('Objetivo');
    expect(getByLabelText('Pasos del creador')).toHaveTextContent('Revisión');
    expect(queryByRole('button', { name: 'Origen' })).not.toBeInTheDocument();
  });

  it('reviews and creates the basic plan without rendering an unused source selector', async () => {
    const onCreatePlan = vi.fn().mockResolvedValue(undefined);
    const { getByRole, queryByText } = renderBuilder(onCreatePlan);

    fireEvent.click(getByRole('button', { name: /continuar/i }));
    expect(queryByText('Elige un punto de partida')).not.toBeInTheDocument();
    fireEvent.click(getByRole('button', { name: /generar pipeline/i }));

    await waitFor(() => expect(onCreatePlan).toHaveBeenCalledWith(objective));
  });

  it('keeps advanced configuration available without replacing the objective', () => {
    const { getByDisplayValue, getByRole } = renderBuilder();

    fireEvent.click(getByRole('button', { name: /configurar opciones avanzadas/i }));

    expect(getByRole('button', { name: /origen/i })).toBeInTheDocument();
    fireEvent.click(getByRole('button', { name: 'Atrás' }));
    expect(getByDisplayValue(objective)).toBeInTheDocument();
  });
});
