package com.spkpvp.client.mixin;

import com.spkpvp.client.SpkPvPClient;
import net.minecraft.client.render.Camera;
import net.minecraft.client.render.GameRenderer;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;

@Mixin(GameRenderer.class)
public abstract class GameRendererMixin {
    @Inject(method = "getFov", at = @At("RETURN"), cancellable = true)
    private void spkpvp$zoom(Camera camera, float tickDelta, boolean changingFov, CallbackInfoReturnable<Double> cir) {
        if (SpkPvPClient.MODULES.zoom.active()) {
            cir.setReturnValue(SpkPvPClient.MODULES.zoom.apply(cir.getReturnValueD()));
        }
    }
}
