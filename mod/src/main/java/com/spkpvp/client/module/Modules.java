package com.spkpvp.client.module;

import com.spkpvp.client.mixin.SimpleOptionAccessor;
import java.time.LocalTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Deque;
import java.util.List;
import net.minecraft.client.gui.DrawContext;
import net.minecraft.client.network.PlayerListEntry;
import net.minecraft.client.network.ServerInfo;
import net.minecraft.client.option.KeyBinding;
import net.minecraft.entity.effect.StatusEffectInstance;
import net.minecraft.item.ItemStack;
import net.minecraft.util.math.MathHelper;

/** Todos os módulos do client. Os ids são os mesmos usados pelo launcher. */
public final class Modules {
    private Modules() {
    }

    // ------------------------------------------------------------------ HUD de texto

    public static final class Fps extends TextHudModule {
        public Fps() {
            super("fps", "FPS", true, 2, 2);
        }

        @Override
        protected String text() {
            return MC.getCurrentFps() + " FPS";
        }
    }

    public static final class Cps extends TextHudModule {
        private static final Deque<Long> LEFT = new ArrayDeque<>();
        private static final Deque<Long> RIGHT = new ArrayDeque<>();

        public Cps() {
            super("cps", "CPS", true, 2, 17);
        }

        /** Registrado pelo MouseMixin a cada clique (0 = esquerdo, 1 = direito). */
        public static synchronized void click(int button) {
            if (button == 0) LEFT.add(System.currentTimeMillis());
            else if (button == 1) RIGHT.add(System.currentTimeMillis());
        }

        private static int count(Deque<Long> clicks) {
            long limit = System.currentTimeMillis() - 1000;
            while (!clicks.isEmpty() && clicks.peekFirst() < limit) clicks.pollFirst();
            return clicks.size();
        }

        public static synchronized int left() {
            return count(LEFT);
        }

        public static synchronized int right() {
            return count(RIGHT);
        }

        @Override
        protected String text() {
            return left() + " | " + right() + " CPS";
        }
    }

    public static final class Ping extends TextHudModule {
        public Ping() {
            super("ping", "Ping", true, 2, 32);
        }

        @Override
        public boolean visible() {
            return super.visible() && MC.getNetworkHandler() != null && !MC.isInSingleplayer();
        }

        @Override
        protected String text() {
            if (MC.player == null || MC.getNetworkHandler() == null) return "0 ms";
            PlayerListEntry entry = MC.getNetworkHandler().getPlayerListEntry(MC.player.getUuid());
            return (entry == null ? 0 : entry.getLatency()) + " ms";
        }
    }

    public static final class Coords extends TextHudModule {
        public Coords() {
            super("coords", "Coordenadas", false, 2, 47);
        }

        @Override
        protected String text() {
            if (MC.player == null) return "X 0 Y 64 Z 0";
            return "X " + MC.player.getBlockX() + " Y " + MC.player.getBlockY() + " Z " + MC.player.getBlockZ()
                + " " + MC.player.getHorizontalFacing().asString().substring(0, 1).toUpperCase();
        }
    }

    public static final class Clock extends TextHudModule {
        private static final DateTimeFormatter FORMAT = DateTimeFormatter.ofPattern("HH:mm");

        public Clock() {
            super("clock", "Relógio", false, 2, 62);
        }

        @Override
        protected String text() {
            return LocalTime.now().format(FORMAT);
        }
    }

    public static final class Server extends TextHudModule {
        public Server() {
            super("server", "Servidor", false, 2, 77);
        }

        @Override
        protected String text() {
            ServerInfo info = MC.getCurrentServerEntry();
            return info == null ? "Singleplayer" : info.address;
        }
    }

    // ------------------------------------------------------------------ keystrokes

    public static final class Keystrokes extends HudModule {
        private static final int KEY = 22;
        private static final int GAP = 2;

        public Keystrokes() {
            super("keystrokes", "Keystrokes", true, 2, 110);
        }

        @Override
        public int width() {
            return KEY * 3 + GAP * 2;
        }

        @Override
        public int height() {
            return KEY * 3 + GAP * 3 + 12;
        }

        private void key(DrawContext ctx, int x, int y, int w, int h, String label, boolean pressed) {
            ctx.fill(x, y, x + w, y + h, pressed ? 0xC8FFFFFF : BACKGROUND);
            int color = pressed ? 0xFF000000 : TEXT;
            ctx.drawText(MC.textRenderer, label, x + (w - MC.textRenderer.getWidth(label)) / 2,
                y + (h - MC.textRenderer.fontHeight) / 2 + 1, color, !pressed);
        }

        private static boolean down(KeyBinding key) {
            return key.isPressed();
        }

        @Override
        public void render(DrawContext ctx, int x, int y) {
            var o = MC.options;
            int step = KEY + GAP;
            key(ctx, x + step, y, KEY, KEY, "W", down(o.forwardKey));
            key(ctx, x, y + step, KEY, KEY, "A", down(o.leftKey));
            key(ctx, x + step, y + step, KEY, KEY, "S", down(o.backKey));
            key(ctx, x + step * 2, y + step, KEY, KEY, "D", down(o.rightKey));
            int half = (width() - GAP) / 2;
            key(ctx, x, y + step * 2, half, KEY, "LMB " + Cps.left(), down(o.attackKey));
            key(ctx, x + half + GAP, y + step * 2, width() - half - GAP, KEY, "RMB " + Cps.right(), down(o.useKey));
            key(ctx, x, y + step * 3, width(), 12, "Space", down(o.jumpKey));
        }
    }

    // ------------------------------------------------------------------ armadura

    public static final class Armor extends HudModule {
        public Armor() {
            super("armor", "Armor Status", true, 10000, 110);
        }

        private List<ItemStack> stacks() {
            List<ItemStack> out = new ArrayList<>();
            if (MC.player == null) return out;
            for (int i = 3; i >= 0; i--) {
                ItemStack s = MC.player.getInventory().getArmorStack(i);
                if (!s.isEmpty()) out.add(s);
            }
            if (!MC.player.getMainHandStack().isEmpty()) out.add(MC.player.getMainHandStack());
            return out;
        }

        @Override
        public boolean visible() {
            return !stacks().isEmpty();
        }

        @Override
        public int width() {
            return 62;
        }

        @Override
        public int height() {
            return Math.max(1, stacks().size()) * 17;
        }

        @Override
        public void render(DrawContext ctx, int x, int y) {
            int row = y;
            for (ItemStack stack : stacks()) {
                ctx.drawItem(stack, x, row);
                ctx.drawItemInSlot(MC.textRenderer, stack, x, row);
                String label = stack.isDamageable()
                    ? String.valueOf(stack.getMaxDamage() - stack.getDamage())
                    : stack.getCount() > 1 ? String.valueOf(stack.getCount()) : "";
                int color = TEXT;
                if (stack.isDamageable()) {
                    float left = 1f - stack.getDamage() / (float) stack.getMaxDamage();
                    color = left > .5f ? 0xFF55FF55 : left > .2f ? 0xFFFFFF55 : 0xFFFF5555;
                }
                ctx.drawText(MC.textRenderer, label, x + 20, row + 4, color, true);
                row += 17;
            }
        }

        @Override
        public void renderPreview(DrawContext ctx, int x, int y) {
            ctx.fill(x, y, x + width(), y + 17, BACKGROUND);
            ctx.drawText(MC.textRenderer, "Armadura", x + 4, y + 5, TEXT, true);
        }
    }

    // ------------------------------------------------------------------ poções

    public static final class Potions extends HudModule {
        private static final String[] ROMAN = {"", " II", " III", " IV", " V", " VI", " VII", " VIII", " IX", " X"};

        public Potions() {
            super("potions", "Efeitos de poção", true, 10000, 2);
        }

        private List<String> lines() {
            List<String> out = new ArrayList<>();
            if (MC.player == null) return out;
            for (StatusEffectInstance effect : MC.player.getStatusEffects()) {
                String name = effect.getEffectType().value().getName().getString();
                int amp = effect.getAmplifier();
                name += amp < ROMAN.length ? ROMAN[amp] : " " + (amp + 1);
                String time;
                if (effect.isInfinite()) {
                    time = "∞";
                } else {
                    int sec = effect.getDuration() / 20;
                    time = String.format("%d:%02d", sec / 60, sec % 60);
                }
                out.add(name + " §7" + time);
            }
            return out;
        }

        @Override
        public boolean visible() {
            return !lines().isEmpty();
        }

        @Override
        public int width() {
            int w = 60;
            for (String line : lines()) w = Math.max(w, MC.textRenderer.getWidth(line) + 8);
            return w;
        }

        @Override
        public int height() {
            return Math.max(1, lines().size()) * 11 + 4;
        }

        @Override
        public void render(DrawContext ctx, int x, int y) {
            List<String> lines = lines();
            ctx.fill(x, y, x + width(), y + height(), BACKGROUND);
            for (int i = 0; i < lines.size(); i++) {
                ctx.drawText(MC.textRenderer, lines.get(i), x + 4, y + 3 + i * 11, TEXT, true);
            }
        }

        @Override
        public void renderPreview(DrawContext ctx, int x, int y) {
            ctx.fill(x, y, x + 90, y + 15, BACKGROUND);
            ctx.drawText(MC.textRenderer, "Velocidade II §70:45", x + 4, y + 3, TEXT, true);
        }
    }

    // ------------------------------------------------------------------ mecânicas

    public static final class ToggleSprint extends TextHudModule {
        private boolean sprinting = true;

        public ToggleSprint() {
            super("togglesprint", "Toggle Sprint", true, 2, 92);
        }

        public void flip() {
            sprinting = !sprinting;
            if (!sprinting) MC.options.sprintKey.setPressed(false);
        }

        @Override
        public void tick() {
            if (isEnabled() && sprinting && MC.player != null && MC.currentScreen == null) {
                MC.options.sprintKey.setPressed(true);
            }
        }

        @Override
        protected void onDisable() {
            if (MC.options != null) MC.options.sprintKey.setPressed(false);
        }

        @Override
        protected String text() {
            return "Sprint " + (sprinting ? "(Toggled)" : "(Off)");
        }
    }

    public static final class Zoom extends Module {
        private double factor = 4;
        private boolean active;
        private boolean savedSmooth;

        public Zoom() {
            super("zoom", "Zoom", "Mecânica", true);
        }

        public boolean active() {
            return active;
        }

        /** Chamado a cada tick com o estado da tecla de zoom. */
        public void update(boolean keyDown) {
            boolean now = isEnabled() && keyDown && MC.currentScreen == null;
            if (now && !active) {
                factor = 4;
                savedSmooth = MC.options.smoothCameraEnabled;
                MC.options.smoothCameraEnabled = true;
            } else if (!now && active) {
                MC.options.smoothCameraEnabled = savedSmooth;
            }
            active = now;
        }

        public void scroll(double amount) {
            factor = MathHelper.clamp(factor * (amount > 0 ? 1.25 : 0.8), 1.5, 50);
        }

        public double apply(double fov) {
            return active ? fov / factor : fov;
        }
    }

    public static final class Fullbright extends Module {
        private Double previous;

        public Fullbright() {
            super("fullbright", "Fullbright", "Visual", false);
        }

        @SuppressWarnings("unchecked")
        private static SimpleOptionAccessor<Double> gamma() {
            return (SimpleOptionAccessor<Double>) (Object) MC.options.getGamma();
        }

        @Override
        public void tick() {
            if (isEnabled()) {
                if (previous == null) previous = MC.options.getGamma().getValue();
                gamma().spkpvp$setValue(16.0);
            }
        }

        @Override
        protected void onDisable() {
            if (previous != null) {
                gamma().spkpvp$setValue(previous);
                previous = null;
            }
        }
    }

    /** Liga/desliga a exibição de capas e asas da loja. */
    public static final class Cosmetics extends Module {
        public Cosmetics() {
            super("cosmetics", "Cosméticos", "Visual", true);
        }
    }
}
