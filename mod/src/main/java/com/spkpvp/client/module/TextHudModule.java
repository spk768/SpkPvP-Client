package com.spkpvp.client.module;

import net.minecraft.client.gui.DrawContext;

/** Módulo de HUD que mostra uma linha de texto numa caixa (estilo Lunar/Badlion). */
public abstract class TextHudModule extends HudModule {
    private static final int PADDING = 4;

    protected TextHudModule(String id, String name, boolean enabledByDefault, int defaultX, int defaultY) {
        super(id, name, enabledByDefault, defaultX, defaultY);
    }

    protected abstract String text();

    @Override
    public int width() {
        return Math.max(56, MC.textRenderer.getWidth(text()) + PADDING * 2);
    }

    @Override
    public int height() {
        return MC.textRenderer.fontHeight + PADDING * 2 - 1;
    }

    @Override
    public void render(DrawContext ctx, int x, int y) {
        String text = text();
        int w = width();
        ctx.fill(x, y, x + w, y + height(), BACKGROUND);
        ctx.drawText(MC.textRenderer, text, x + (w - MC.textRenderer.getWidth(text)) / 2, y + PADDING, TEXT, true);
    }
}
