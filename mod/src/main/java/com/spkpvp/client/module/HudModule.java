package com.spkpvp.client.module;

import net.minecraft.client.gui.DrawContext;

/** Módulo desenhado no HUD, em uma posição que o jogador arrasta no editor. */
public abstract class HudModule extends Module {
    public static final int BACKGROUND = 0x6F000000;
    public static final int TEXT = 0xFFFFFFFF;

    private int x;
    private int y;

    protected HudModule(String id, String name, boolean enabledByDefault, int defaultX, int defaultY) {
        super(id, name, "HUD", enabledByDefault);
        this.x = defaultX;
        this.y = defaultY;
    }

    public int x() {
        return x;
    }

    public int y() {
        return y;
    }

    public void setPosition(int x, int y) {
        this.x = x;
        this.y = y;
    }

    /** Posição limitada à tela atual (a janela pode ter mudado de tamanho). */
    public int renderX() {
        return Math.max(0, Math.min(x, MC.getWindow().getScaledWidth() - width()));
    }

    public int renderY() {
        return Math.max(0, Math.min(y, MC.getWindow().getScaledHeight() - height()));
    }

    public abstract int width();

    public abstract int height();

    /** Desenha o módulo com o canto superior esquerdo em (x, y). */
    public abstract void render(DrawContext ctx, int x, int y);

    /** Se há algo para mostrar agora (ex.: sem efeitos de poção, nada aparece). */
    public boolean visible() {
        return MC.player != null;
    }

    /** Conteúdo de exemplo para o editor de HUD quando {@link #visible()} é falso. */
    public void renderPreview(DrawContext ctx, int x, int y) {
        render(ctx, x, y);
    }
}
