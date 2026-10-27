package com.spkpvp.client.gui;

import com.spkpvp.client.SpkPvPClient;
import com.spkpvp.client.module.Module;
import java.util.List;
import net.minecraft.client.gui.DrawContext;
import net.minecraft.client.gui.screen.Screen;
import net.minecraft.client.gui.widget.ButtonWidget;
import net.minecraft.text.Text;
import net.minecraft.util.Formatting;

/** Menu do client (Shift direito): liga/desliga módulos e abre o editor de HUD. */
public class ClickGuiScreen extends Screen {
    private static final int BUTTON_W = 140;
    private static final int BUTTON_H = 20;
    private static final int GAP = 4;
    private static final int COLUMNS = 3;

    public ClickGuiScreen() {
        super(Text.literal("SpkPvP Client"));
    }

    @Override
    protected void init() {
        List<Module> modules = SpkPvPClient.MODULES.all();
        int totalW = COLUMNS * BUTTON_W + (COLUMNS - 1) * GAP;
        int rows = (modules.size() + COLUMNS - 1) / COLUMNS;
        int left = (width - totalW) / 2;
        int top = Math.max(40, (height - rows * (BUTTON_H + GAP) - 40) / 2);
        for (int i = 0; i < modules.size(); i++) {
            Module m = modules.get(i);
            int x = left + (i % COLUMNS) * (BUTTON_W + GAP);
            int y = top + (i / COLUMNS) * (BUTTON_H + GAP);
            addDrawableChild(ButtonWidget.builder(label(m), b -> {
                m.toggle();
                b.setMessage(label(m));
            }).dimensions(x, y, BUTTON_W, BUTTON_H).build());
        }
        int bottom = top + rows * (BUTTON_H + GAP) + 10;
        addDrawableChild(ButtonWidget.builder(Text.literal("Editar HUD"), b -> client.setScreen(new HudEditorScreen(this)))
            .dimensions(width / 2 - BUTTON_W - GAP / 2, bottom, BUTTON_W, BUTTON_H).build());
        addDrawableChild(ButtonWidget.builder(Text.literal("Fechar"), b -> close())
            .dimensions(width / 2 + GAP / 2, bottom, BUTTON_W, BUTTON_H).build());
    }

    private static Text label(Module m) {
        return Text.literal(m.name() + ": ")
            .append(m.isEnabled() ? Text.literal("ON").formatted(Formatting.GREEN)
                : Text.literal("OFF").formatted(Formatting.RED));
    }

    @Override
    public void render(DrawContext ctx, int mouseX, int mouseY, float delta) {
        super.render(ctx, mouseX, mouseY, delta);
        ctx.drawCenteredTextWithShadow(textRenderer, Text.literal("SpkPvP Client").formatted(Formatting.BOLD),
            width / 2, 16, 0xFFFFFF);
        ctx.drawCenteredTextWithShadow(textRenderer, "Cosméticos: compre e equipe pelo launcher",
            width / 2, height - 14, 0xA0A0A0);
    }

    @Override
    public void removed() {
        SpkPvPClient.MODULES.save();
    }

    @Override
    public boolean shouldPause() {
        return false;
    }
}
