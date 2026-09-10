export interface StartScreenInput {
  startScreenRequested: boolean;
  isDocked: boolean;
  turnCount: number;
  activeConversationId?: string;
}

/**
 * Autoridad única sobre la pantalla de bienvenida del chat.
 *
 * La bienvenida sólo debe interponerse cuando no hay nada que retomar. Si la
 * conversación ya tiene turnos, mostrarla obliga al usuario a atravesar una
 * pantalla intermedia cuya acción principal crea una conversación nueva, lo que
 * añade fricción y arriesga perder el hilo activo.
 */
export function shouldOpenStartScreen(input: StartScreenInput): boolean {
  if (input.isDocked) return false;
  if (!input.startScreenRequested) return false;
  // An empty, persisted conversation is still a conversation to resume. Do
  // not place the welcome decision screen in front of its composer.
  if (input.activeConversationId) return false;
  return input.turnCount === 0;
}
