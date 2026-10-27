package com.spkpvp.client.gui;

import com.spkpvp.client.SpkPvPClient;
import com.spkpvp.client.module.HudModule;
import net.minecraft.client.gui.DrawContext;
import net.minecraft.client.gui.screen.Screen;
import net.minecraft.text.Text;

/** Editor de HUD: arraste os módulos ativos para reposicioná-los. */
public class HudEditorScreen extends Screen {
    private final Screen parent;
    private HudModule dragging;
    private int offsetX;
    private int offsetY;

    public HudEditorScreen(Screen parent) {
        super(Text.literal("Editar HUD"));
        this.parent = parent;
    }

    @Override
    public void renderBackground(DrawContext ctx, int mouseX, int mouseY, float delta) {
        ctx.fill(0, 0, width, height, 0x40000000);
    }

    @Override
    public void render(DrawContext ctx, int mouseX, int mouseY, float delta) {
        super.render(ctx, mouseX, mouseY, delta);
        for (HudModule m : SpkPvPClient.MODULES.hud()) {
            if (!m.isEnabled()) continue;
            int x = m.renderX();
            int y = m.renderY();
            if (m.visible()) m.render(ctx, x, y);
            else m.renderPreview(ctx, x, y);
            boolean hover = m == dragging || inside(m, mouseX, mouseY);
            ctx.drawBorder(x - 1, y - 1, m.width() + 2, m.height() + 2, hover ? 0xFFFFFFFF : 0x80FFFFFF);
        }
        ctx.drawCenteredTextWithShadow(textRenderer, "Arraste os módulos. ESC para salvar.", width / 2, height / 2,
            0xFFFFFF);
    }

    private static boolean inside(HudModule m, double mx, double my) {
        return mx >= m.renderX() && mx < m.renderX() + m.width() && my >= m.renderY() && my < m.renderY() + m.height();
    }

    @Override
    public boolean mouseClicked(double mouseX, double mouseY, int button) {
        if (button == 0) {
            for (HudModule m : SpkPvPClient.MODULES.hud()) {
                if (m.isEnabled() && inside(m, mouseX, mouseY)) {
                    dragging = m;
                    offsetX = (int) mouseX - m.renderX();
                    offsetY = (int) mouseY - m.renderY();
                    return true;
                }
            }
        }
        return super.mouseClicked(mouseX, mouseY, button);
    }

    @Override
    public boolean mouseDragged(double mouseX, double mouseY, int button, double deltaX, double deltaY) {
        if (dragging != null) {
            int x = Math.max(0, Math.min((int) mouseX - offsetX, width - dragging.width()));
            int y = Math.max(0, Math.min((int) mouseY - offsetY, height - dragging.height()));
            // encostado na borda direita fica preso a ela mesmo se a janela mudar de tamanho
            dragging.setPosition(x + dragging.width() >= width ? 10000 : x, y);
            return true;
        }
        return super.mouseDragged(mouseX, mouseY, button, deltaX, deltaY);
    }

    @Override
    public boolean mouseReleased(double mouseX, double mouseY, int button) {
        dragging = null;
        return super.mouseReleased(mouseX, mouseY, button);
    }

    @Override
    public void close() {
        SpkPvPClient.MODULES.save();
        client.setScreen(parent);
    }

    @Override
    public boolean shouldPause() {
        return false;
    }
}
