package com.spkpvp.client.mixin;

import com.spkpvp.client.cosmetics.CosmeticsManager;
import net.minecraft.client.network.AbstractClientPlayerEntity;
import net.minecraft.client.util.SkinTextures;
import net.minecraft.util.Identifier;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;

/** Troca a capa do jogador pela capa equipada na loja do SpkPvP. */
@Mixin(AbstractClientPlayerEntity.class)
public abstract class AbstractClientPlayerEntityMixin {
    @Inject(method = "getSkinTextures", at = @At("RETURN"), cancellable = true)
    private void spkpvp$cape(CallbackInfoReturnable<SkinTextures> cir) {
        AbstractClientPlayerEntity self = (AbstractClientPlayerEntity) (Object) this;
        Identifier cape = CosmeticsManager.get().cape(self.getUuid());
        if (cape != null) {
            SkinTextures t = cir.getReturnValue();
            cir.setReturnValue(new SkinTextures(t.texture(), t.textureUrl(), cape, cape, t.model(), t.secure()));
        }
    }
}
