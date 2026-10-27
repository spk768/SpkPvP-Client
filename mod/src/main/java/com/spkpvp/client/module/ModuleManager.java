package com.spkpvp.client.module;

import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import com.spkpvp.client.SpkPvPClient;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import net.fabricmc.loader.api.FabricLoader;
import net.minecraft.client.MinecraftClient;
import net.minecraft.client.gui.DrawContext;

/**
 * Lista de módulos e persistência em config/spkpvp/modules.json, o mesmo
 * arquivo que o launcher edita: {"fps": {"enabled": true, "x": 2, "y": 2}, ...}
 */
public final class ModuleManager {
    private static final Gson GSON = new GsonBuilder().setPrettyPrinting().create();

    public final Modules.Fps fps = new Modules.Fps();
    public final Modules.Cps cps = new Modules.Cps();
    public final Modules.Keystrokes keystrokes = new Modules.Keystrokes();
    public final Modules.Armor armor = new Modules.Armor();
    public final Modules.Potions potions = new Modules.Potions();
    public final Modules.Coords coords = new Modules.Coords();
    public final Modules.Ping ping = new Modules.Ping();
    public final Modules.Clock clock = new Modules.Clock();
    public final Modules.Server server = new Modules.Server();
    public final Modules.ToggleSprint toggleSprint = new Modules.ToggleSprint();
    public final Modules.Zoom zoom = new Modules.Zoom();
    public final Modules.Fullbright fullbright = new Modules.Fullbright();
    public final Modules.Cosmetics cosmetics = new Modules.Cosmetics();

    private final List<Module> all = List.of(fps, cps, keystrokes, armor, potions, coords, ping, clock, server,
        toggleSprint, zoom, fullbright, cosmetics);

    public List<Module> all() {
        return all;
    }

    public List<HudModule> hud() {
        List<HudModule> out = new ArrayList<>();
        for (Module m : all) {
            if (m instanceof HudModule h) out.add(h);
        }
        return out;
    }

    private static Path file() {
        return FabricLoader.getInstance().getConfigDir().resolve("spkpvp").resolve("modules.json");
    }

    public void load() {
        Path path = file();
        if (!Files.isRegularFile(path)) return;
        try {
            JsonObject root = JsonParser.parseString(Files.readString(path, StandardCharsets.UTF_8)).getAsJsonObject();
            for (Module m : all) {
                JsonElement el = root.get(m.id());
                if (el == null || !el.isJsonObject()) continue;
                JsonObject o = el.getAsJsonObject();
                if (o.has("enabled")) m.setEnabled(o.get("enabled").getAsBoolean());
                if (m instanceof HudModule h && o.has("x") && o.has("y")) {
                    h.setPosition(o.get("x").getAsInt(), o.get("y").getAsInt());
                }
            }
        } catch (IOException | RuntimeException e) {
            SpkPvPClient.LOGGER.warn("Configuração do SpkPvP inválida, usando padrões", e);
        }
    }

    public void save() {
        JsonObject root = new JsonObject();
        for (Module m : all) {
            JsonObject o = new JsonObject();
            o.addProperty("enabled", m.isEnabled());
            if (m instanceof HudModule h) {
                o.addProperty("x", h.x());
                o.addProperty("y", h.y());
            }
            root.add(m.id(), o);
        }
        try {
            Files.createDirectories(file().getParent());
            Files.writeString(file(), GSON.toJson(root), StandardCharsets.UTF_8);
        } catch (IOException e) {
            SpkPvPClient.LOGGER.warn("Não foi possível salvar a configuração do SpkPvP", e);
        }
    }

    public void tick() {
        for (Module m : all) m.tick();
    }

    public void renderHud(DrawContext ctx) {
        MinecraftClient mc = MinecraftClient.getInstance();
        if (mc.options.hudHidden || mc.getDebugHud().shouldShowDebugHud()) return;
        for (HudModule m : hud()) {
            if (m.isEnabled() && m.visible()) m.render(ctx, m.renderX(), m.renderY());
        }
    }
}
