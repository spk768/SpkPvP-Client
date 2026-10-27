package com.spkpvp.client.cosmetics;

import net.minecraft.client.network.AbstractClientPlayerEntity;
import net.minecraft.client.render.OverlayTexture;
import net.minecraft.client.render.RenderLayer;
import net.minecraft.client.render.VertexConsumer;
import net.minecraft.client.render.VertexConsumerProvider;
import net.minecraft.client.render.entity.feature.FeatureRenderer;
import net.minecraft.client.render.entity.feature.FeatureRendererContext;
import net.minecraft.client.render.entity.model.PlayerEntityModel;
import net.minecraft.client.util.math.MatrixStack;
import net.minecraft.util.Identifier;
import net.minecraft.util.math.MathHelper;
import net.minecraft.util.math.RotationAxis;

/** Desenha as asas compradas na loja: dois planos texturizados nas costas que batem devagar. */
public class WingsFeatureRenderer
    extends FeatureRenderer<AbstractClientPlayerEntity, PlayerEntityModel<AbstractClientPlayerEntity>> {

    private static final float SIZE = 1.0f;

    public WingsFeatureRenderer(
        FeatureRendererContext<AbstractClientPlayerEntity, PlayerEntityModel<AbstractClientPlayerEntity>> context) {
        super(context);
    }

    @Override
    public void render(MatrixStack matrices, VertexConsumerProvider vertexConsumers, int light,
                       AbstractClientPlayerEntity player, float limbAngle, float limbDistance, float tickDelta,
                       float animationProgress, float headYaw, float headPitch) {
        if (player.isInvisible() || player.isSpectator()) return;
        Identifier texture = CosmeticsManager.get().wings(player.getUuid());
        if (texture == null) return;

        // abre mais rápido ao voar/cair, devagar parado
        float speed = player.isOnGround() ? 0.12f : 0.35f;
        float flap = 18f + MathHelper.sin(animationProgress * speed) * 12f;
        VertexConsumer buffer = vertexConsumers.getBuffer(RenderLayer.getEntityCutoutNoCull(texture));

        matrices.push();
        getContextModel().body.rotate(matrices);
        matrices.translate(0.0f, 0.05f, 0.15f);
        for (int side = -1; side <= 1; side += 2) {
            matrices.push();
            matrices.translate(side * 0.06f, 0.0f, 0.0f);
            matrices.multiply(RotationAxis.POSITIVE_Y.rotationDegrees(side * -flap));
            quad(matrices, buffer, light, side);
            matrices.pop();
        }
        matrices.pop();
    }

    /** Plano vertical que sai das costas para o lado {@code side} (-1 esquerda, 1 direita). */
    private static void quad(MatrixStack matrices, VertexConsumer buffer, int light, int side) {
        MatrixStack.Entry entry = matrices.peek();
        float x0 = 0f;
        float x1 = side * SIZE;
        float top = -0.35f;
        float bottom = top + SIZE;
        // a textura é desenhada com a raiz da asa (u=0) junto ao corpo
        vertex(buffer, entry, x0, top, 0f, 0f, light);
        vertex(buffer, entry, x0, bottom, 0f, 1f, light);
        vertex(buffer, entry, x1, bottom, 1f, 1f, light);
        vertex(buffer, entry, x1, top, 1f, 0f, light);
    }

    private static void vertex(VertexConsumer buffer, MatrixStack.Entry entry, float x, float y, float u, float v,
                               int light) {
        buffer.vertex(entry, x, y, 0f)
            .color(0xFFFFFFFF)
            .texture(u, v)
            .overlay(OverlayTexture.DEFAULT_UV)
            .light(light)
            .normal(entry, 0f, 0f, 1f);
    }
}
