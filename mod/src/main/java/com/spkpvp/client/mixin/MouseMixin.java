package com.spkpvp.client.mixin;

import com.spkpvp.client.SpkPvPClient;
import com.spkpvp.client.module.Modules;
import net.minecraft.client.MinecraftClient;
import net.minecraft.client.Mouse;
import org.lwjgl.glfw.GLFW;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

@Mixin(Mouse.class)
public abstract class MouseMixin {
    @Inject(method = "onMouseButton", at = @At("HEAD"))
    private void spkpvp$countClick(long window, int button, int action, int mods, CallbackInfo ci) {
        if (action == GLFW.GLFW_PRESS && MinecraftClient.getInstance().currentScreen == null) {
            Modules.Cps.click(button);
        }
    }

    @Inject(method = "onMouseScroll", at = @At("HEAD"), cancellable = true)
    private void spkpvp$zoomScroll(long window, double horizontal, double vertical, CallbackInfo ci) {
        if (SpkPvPClient.MODULES.zoom.active() && vertical != 0) {
            SpkPvPClient.MODULES.zoom.scroll(vertical);
            ci.cancel();
        }
    }
}
