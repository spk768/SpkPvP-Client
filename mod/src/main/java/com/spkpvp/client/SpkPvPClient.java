package com.spkpvp.client;

import com.spkpvp.client.cosmetics.CosmeticsManager;
import com.spkpvp.client.cosmetics.WingsFeatureRenderer;
import com.spkpvp.client.gui.ClickGuiScreen;
import com.spkpvp.client.gui.HudEditorScreen;
import com.spkpvp.client.module.ModuleManager;
import net.fabricmc.api.ClientModInitializer;
import net.fabricmc.fabric.api.client.event.lifecycle.v1.ClientLifecycleEvents;
import net.fabricmc.fabric.api.client.event.lifecycle.v1.ClientTickEvents;
import net.fabricmc.fabric.api.client.keybinding.v1.KeyBindingHelper;
import net.fabricmc.fabric.api.client.rendering.v1.HudRenderCallback;
import net.fabricmc.fabric.api.client.rendering.v1.LivingEntityFeatureRendererRegistrationCallback;
import net.minecraft.client.option.KeyBinding;
import net.minecraft.client.render.entity.PlayerEntityRenderer;
import net.minecraft.client.util.InputUtil;
import org.lwjgl.glfw.GLFW;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

public final class SpkPvPClient implements ClientModInitializer {
    public static final String MOD_ID = "spkpvp";
    public static final Logger LOGGER = LoggerFactory.getLogger("SpkPvP");
    public static final ModuleManager MODULES = new ModuleManager();

    private static KeyBinding menuKey;
    private static KeyBinding zoomKey;
    private static KeyBinding sprintKey;

    @Override
    public void onInitializeClient() {
        MODULES.load();
        CosmeticsManager.get().loadConfig();

        menuKey = register("key.spkpvp.menu", GLFW.GLFW_KEY_RIGHT_SHIFT);
        zoomKey = register("key.spkpvp.zoom", GLFW.GLFW_KEY_C);
        sprintKey = register("key.spkpvp.sprint", GLFW.GLFW_KEY_V);

        ClientTickEvents.END_CLIENT_TICK.register(client -> {
            while (menuKey.wasPressed()) {
                if (client.currentScreen == null) client.setScreen(new ClickGuiScreen());
            }
            while (sprintKey.wasPressed()) MODULES.toggleSprint.flip();
            MODULES.zoom.update(zoomKey.isPressed());
            MODULES.tick();
        });

        HudRenderCallback.EVENT.register((ctx, tickCounter) -> {
            var client = net.minecraft.client.MinecraftClient.getInstance();
            if (!(client.currentScreen instanceof HudEditorScreen)) MODULES.renderHud(ctx);
        });

        LivingEntityFeatureRendererRegistrationCallback.EVENT.register((type, renderer, helper, context) -> {
            if (renderer instanceof PlayerEntityRenderer player) helper.register(new WingsFeatureRenderer(player));
        });

        ClientLifecycleEvents.CLIENT_STOPPING.register(client -> MODULES.save());
        LOGGER.info("SpkPvP Client carregado");
    }

    private static KeyBinding register(String name, int key) {
        return KeyBindingHelper.registerKeyBinding(new KeyBinding(name, InputUtil.Type.KEYSYM, key, "category.spkpvp"));
    }
}
