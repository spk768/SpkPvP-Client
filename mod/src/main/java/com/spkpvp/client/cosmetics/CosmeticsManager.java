package com.spkpvp.client.cosmetics;

import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import com.spkpvp.client.SpkPvPClient;
import java.io.ByteArrayInputStream;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Duration;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.Executors;
import java.util.concurrent.Semaphore;
import net.fabricmc.loader.api.FabricLoader;
import net.minecraft.client.MinecraftClient;
import net.minecraft.client.texture.NativeImage;
import net.minecraft.client.texture.NativeImageBackedTexture;
import net.minecraft.util.Identifier;

/**
 * Busca no servidor da loja os cosméticos equipados de cada jogador visível
 * (GET /api/players/{uuid}/cosmetics) e registra as texturas no jogo.
 */
public final class CosmeticsManager {
    private static final CosmeticsManager INSTANCE = new CosmeticsManager();
    private static final long REFRESH_MS = 60_000;
    private static final long RETRY_MS = 5 * 60_000;

    private record Entry(long fetched, String cape, String wings) {
    }

    private final HttpClient http = HttpClient.newBuilder()
        .connectTimeout(Duration.ofSeconds(5))
        .executor(Executors.newFixedThreadPool(2, r -> {
            Thread t = new Thread(r, "SpkPvP-Cosmetics");
            t.setDaemon(true);
            return t;
        }))
        .build();
    private final Map<UUID, Entry> players = new ConcurrentHashMap<>();
    private final Map<UUID, Boolean> pending = new ConcurrentHashMap<>();
    private final Map<String, Identifier> textures = new ConcurrentHashMap<>();
    private final Map<String, Long> failedTextures = new ConcurrentHashMap<>();
    private final Map<String, Boolean> loading = new ConcurrentHashMap<>();
    private final Semaphore inFlight = new Semaphore(8);
    private String apiUrl = "http://127.0.0.1:8787";

    public static CosmeticsManager get() {
        return INSTANCE;
    }

    /** Lê config/spkpvp/client.json, escrito pelo launcher. */
    public void loadConfig() {
        Path file = FabricLoader.getInstance().getConfigDir().resolve("spkpvp").resolve("client.json");
        try {
            if (Files.isRegularFile(file)) {
                JsonObject o = JsonParser.parseString(Files.readString(file, StandardCharsets.UTF_8)).getAsJsonObject();
                if (o.has("api_url")) apiUrl = o.get("api_url").getAsString().replaceAll("/+$", "");
            }
        } catch (Exception e) {
            SpkPvPClient.LOGGER.warn("client.json inválido", e);
        }
    }

    public Identifier cape(UUID uuid) {
        Entry e = entry(uuid);
        return e == null ? null : texture(e.cape());
    }

    public Identifier wings(UUID uuid) {
        Entry e = entry(uuid);
        return e == null ? null : texture(e.wings());
    }

    private Entry entry(UUID uuid) {
        if (!SpkPvPClient.MODULES.cosmetics.isEnabled()) return null;
        Entry e = players.get(uuid);
        if (e == null || System.currentTimeMillis() - e.fetched() > REFRESH_MS) fetch(uuid);
        return e;
    }

    private void fetch(UUID uuid) {
        if (pending.putIfAbsent(uuid, true) != null) return;
        if (!inFlight.tryAcquire()) {
            pending.remove(uuid);
            return;
        }
        String id = uuid.toString().replace("-", "");
        HttpRequest req = HttpRequest.newBuilder(URI.create(apiUrl + "/api/players/" + id + "/cosmetics"))
            .timeout(Duration.ofSeconds(10)).header("User-Agent", "SpkPvP-Mod").GET().build();
        http.sendAsync(req, HttpResponse.BodyHandlers.ofString()).whenComplete((res, err) -> {
            try {
                if (err == null && res.statusCode() == 200) {
                    JsonObject o = JsonParser.parseString(res.body()).getAsJsonObject();
                    players.put(uuid, new Entry(System.currentTimeMillis(), url(o, "cape"), url(o, "wings")));
                } else {
                    // servidor fora do ar: tenta de novo mais tarde, sem cosméticos até lá
                    Entry old = players.get(uuid);
                    players.put(uuid, new Entry(System.currentTimeMillis() + RETRY_MS - REFRESH_MS,
                        old == null ? null : old.cape(), old == null ? null : old.wings()));
                }
            } catch (RuntimeException e) {
                SpkPvPClient.LOGGER.debug("Resposta de cosméticos inválida", e);
            } finally {
                pending.remove(uuid);
                inFlight.release();
            }
        });
    }

    private static String url(JsonObject o, String slot) {
        JsonElement el = o.get(slot);
        if (el == null || !el.isJsonObject() || !el.getAsJsonObject().has("texture")) return null;
        return el.getAsJsonObject().get("texture").getAsString();
    }

    private Identifier texture(String url) {
        if (url == null) return null;
        Identifier id = textures.get(url);
        if (id != null) return id;
        Long failed = failedTextures.get(url);
        if (failed != null && System.currentTimeMillis() - failed < RETRY_MS) return null;
        if (loading.putIfAbsent(url, true) == null) download(url);
        return null;
    }

    private void download(String url) {
        HttpRequest req = HttpRequest.newBuilder(URI.create(url)).timeout(Duration.ofSeconds(15))
            .header("User-Agent", "SpkPvP-Mod").GET().build();
        http.sendAsync(req, HttpResponse.BodyHandlers.ofByteArray()).whenComplete((res, err) -> {
            if (err != null || res.statusCode() != 200) {
                failedTextures.put(url, System.currentTimeMillis());
                loading.remove(url);
                return;
            }
            byte[] bytes = res.body();
            MinecraftClient.getInstance().execute(() -> {
                try {
                    NativeImage image = NativeImage.read(new ByteArrayInputStream(bytes));
                    Identifier id = Identifier.of(SpkPvPClient.MOD_ID,
                        "cosmetics/" + Integer.toHexString(url.hashCode()));
                    MinecraftClient.getInstance().getTextureManager()
                        .registerTexture(id, new NativeImageBackedTexture(image));
                    textures.put(url, id);
                } catch (Exception e) {
                    failedTextures.put(url, System.currentTimeMillis());
                    SpkPvPClient.LOGGER.warn("Textura de cosmético inválida: {}", url, e);
                } finally {
                    loading.remove(url);
                }
            });
        });
    }
}
