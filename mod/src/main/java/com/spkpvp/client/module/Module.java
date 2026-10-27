package com.spkpvp.client.module;

import net.minecraft.client.MinecraftClient;

/** Um recurso do client que pode ser ligado e desligado (no menu ou pelo launcher). */
public abstract class Module {
    protected static final MinecraftClient MC = MinecraftClient.getInstance();

    private final String id;
    private final String name;
    private final String category;
    private boolean enabled;

    protected Module(String id, String name, String category, boolean enabledByDefault) {
        this.id = id;
        this.name = name;
        this.category = category;
        this.enabled = enabledByDefault;
    }

    public String id() {
        return id;
    }

    public String name() {
        return name;
    }

    public String category() {
        return category;
    }

    public boolean isEnabled() {
        return enabled;
    }

    public void setEnabled(boolean enabled) {
        if (this.enabled != enabled) {
            this.enabled = enabled;
            if (enabled) onEnable();
            else onDisable();
        }
    }

    public void toggle() {
        setEnabled(!enabled);
    }

    protected void onEnable() {
    }

    protected void onDisable() {
    }

    /** Chamado no fim de cada tick do cliente, ligado ou não. */
    public void tick() {
    }
}
