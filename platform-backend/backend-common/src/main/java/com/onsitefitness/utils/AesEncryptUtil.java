package com.onsitefitness.utils;

import javax.crypto.Cipher;
import javax.crypto.spec.GCMParameterSpec;
import javax.crypto.spec.SecretKeySpec;
import java.nio.charset.StandardCharsets;
import java.security.SecureRandom;
import java.util.Base64;

/**
 * AES 对称加密工具，用于敏感信息(如身份证号)加密存储。
 *
 * <p>§6.22：由 ECB 升级为 AES-GCM（认证加密）——随机 12B IV + 128bit 认证标签，
 * 密文 = Base64(iv ‖ ciphertext ‖ tag)，杜绝 ECB 的确定性密文/填充分组弱点。
 *
 * <p>密钥长度：必须为 16/24/32 字节（对应 AES-128/192/256），否则抛异常快速失败。
 *
 * <p>灰度迁移：历史数据仍是 ECB，读时 {@link #decrypt} 先试 GCM、失败回落
 * {@link #decodeLegacy}；迁移脚本可显式调 {@code decodeLegacy} 读旧数据后重新
 * {@code encrypt} 落新格式。
 */
public class AesEncryptUtil {

    private static final int GCM_IV_LEN = 12;                       // GCM 推荐 IV 长度
    private static final int GCM_TAG_BITS = 128;                    // 128bit 认证标签
    private static final String GCM_TRANSFORMATION = "AES/GCM/NoPadding";
    private static final String LEGACY_TRANSFORMATION = "AES/ECB/PKCS5Padding";

    /**
     * 加密（GCM，返回 Base64(iv ‖ ciphertext ‖ tag)）
     */
    public static String encrypt(String plainText, String key) {
        if (plainText == null || plainText.isEmpty()) {
            return plainText;
        }
        try {
            SecretKeySpec keySpec = keySpec(key);
            byte[] iv = new byte[GCM_IV_LEN];
            new SecureRandom().nextBytes(iv);
            Cipher cipher = Cipher.getInstance(GCM_TRANSFORMATION);
            cipher.init(Cipher.ENCRYPT_MODE, keySpec, new GCMParameterSpec(GCM_TAG_BITS, iv));
            byte[] encrypted = cipher.doFinal(plainText.getBytes(StandardCharsets.UTF_8)); // 已含 tag
            byte[] out = new byte[GCM_IV_LEN + encrypted.length];
            System.arraycopy(iv, 0, out, 0, GCM_IV_LEN);
            System.arraycopy(encrypted, 0, out, GCM_IV_LEN, encrypted.length);
            return Base64.getEncoder().encodeToString(out);
        } catch (Exception e) {
            throw new RuntimeException("敏感信息加密失败", e);
        }
    }

    /**
     * 解密（优先 GCM，失败回落 legacy ECB，兼容灰度迁移期的历史数据）。
     */
    public static String decrypt(String cipherText, String key) {
        if (cipherText == null || cipherText.isEmpty()) {
            return cipherText;
        }
        try {
            return decryptGcm(cipherText, key);
        } catch (Exception gcmEx) {
            // 历史数据仍是 ECB，回落 legacy 解密；legacy 失败则原样返回（兼容明文种子数据）
            return decodeLegacy(cipherText, key);
        }
    }

    /**
     * 读取历史 ECB 密文（灰度迁移脚本用）：旧格式 = Base64(ECB 密文)。
     * 失败时原样返回，兼容明文旧数据/种子数据。
     */
    public static String decodeLegacy(String cipherText, String key) {
        if (cipherText == null || cipherText.isEmpty()) {
            return cipherText;
        }
        try {
            SecretKeySpec keySpec = keySpec(key);
            Cipher cipher = Cipher.getInstance(LEGACY_TRANSFORMATION);
            cipher.init(Cipher.DECRYPT_MODE, keySpec);
            byte[] decrypted = cipher.doFinal(Base64.getDecoder().decode(cipherText));
            return new String(decrypted, StandardCharsets.UTF_8);
        } catch (Exception e) {
            return cipherText;
        }
    }

    private static String decryptGcm(String cipherText, String key) throws Exception {
        SecretKeySpec keySpec = keySpec(key);
        byte[] raw = Base64.getDecoder().decode(cipherText);
        if (raw.length < GCM_IV_LEN + (GCM_TAG_BITS / 8)) {
            throw new IllegalArgumentException("密文长度不合法（非 GCM 格式）");
        }
        byte[] iv = new byte[GCM_IV_LEN];
        System.arraycopy(raw, 0, iv, 0, GCM_IV_LEN);
        byte[] encrypted = new byte[raw.length - GCM_IV_LEN];
        System.arraycopy(raw, GCM_IV_LEN, encrypted, 0, encrypted.length);
        Cipher cipher = Cipher.getInstance(GCM_TRANSFORMATION);
        cipher.init(Cipher.DECRYPT_MODE, keySpec, new GCMParameterSpec(GCM_TAG_BITS, iv));
        return new String(cipher.doFinal(encrypted), StandardCharsets.UTF_8);
    }

    private static SecretKeySpec keySpec(String key) {
        byte[] keyBytes = key.getBytes(StandardCharsets.UTF_8);
        if (keyBytes.length != 16 && keyBytes.length != 24 && keyBytes.length != 32) {
            throw new IllegalArgumentException(
                    "AES 密钥长度必须为 16/24/32 字节，当前 " + keyBytes.length);
        }
        return new SecretKeySpec(keyBytes, "AES");
    }
}
