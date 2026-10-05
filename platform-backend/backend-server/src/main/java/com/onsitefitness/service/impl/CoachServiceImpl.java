package com.onsitefitness.service.impl;

import com.github.pagehelper.Page;
import com.github.pagehelper.PageHelper;
import com.onsitefitness.annotation.AuditLog;
import com.onsitefitness.constant.JwtClaimsConstant;
import com.onsitefitness.constant.MessageConstant;
import com.onsitefitness.dto.CoachAuditDTO;
import com.onsitefitness.dto.CoachLoginDTO;
import com.onsitefitness.dto.CoachPageQueryDTO;
import com.onsitefitness.dto.CoachRegisterDTO;
import com.onsitefitness.entity.Coach;
import com.onsitefitness.entity.CoachCertificate;
import com.onsitefitness.exception.AccountLockedException;
import com.onsitefitness.exception.AccountNotFoundException;
import com.onsitefitness.exception.PasswordErrorException;
import com.onsitefitness.mapper.CoachCertificateMapper;
import com.onsitefitness.mapper.CoachMapper;
import com.onsitefitness.properties.JwtProperties;
import com.onsitefitness.result.PageResult;
import com.onsitefitness.service.CoachService;
import com.onsitefitness.service.TokenBlacklistService;
import com.onsitefitness.utils.AesEncryptUtil;
import com.onsitefitness.utils.JwtUtil;
import com.onsitefitness.vo.CoachLoginVO;
import com.onsitefitness.vo.CoachVO;
import org.springframework.beans.BeanUtils;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

@Service
public class CoachServiceImpl implements CoachService {

    @Autowired
    private CoachMapper coachMapper;
    @Autowired
    private CoachCertificateMapper coachCertificateMapper;
    @Autowired
    private JwtProperties jwtProperties;
    @Autowired
    private TokenBlacklistService tokenBlacklistService;

    /** 密码哈希：BCrypt（无盐 MD5 已弃用，见 §5.5 安全审查） */
    private final BCryptPasswordEncoder passwordEncoder = new BCryptPasswordEncoder();

    @Value("${onsite.encrypt.aes-key}")
    private String aesKey;

    /**
     * 教练入驻
     */
    @Override
    @Transactional
    public Long register(CoachRegisterDTO coachRegisterDTO) {
        Coach coach = Coach.builder()
                .name(coachRegisterDTO.getName())
                .phone(coachRegisterDTO.getPhone())
                .password(passwordEncoder.encode(coachRegisterDTO.getPassword()))
                .sex(coachRegisterDTO.getSex())
                .avatar(coachRegisterDTO.getAvatar())
                .idNumber(AesEncryptUtil.encrypt(coachRegisterDTO.getIdNumber(), aesKey))
                .level(coachRegisterDTO.getLevel())
                .rating(new BigDecimal("5.00"))
                .serviceRadiusKm(coachRegisterDTO.getServiceRadiusKm())
                .cityCode(coachRegisterDTO.getCityCode())
                .cityName(coachRegisterDTO.getCityName())
                .bio(coachRegisterDTO.getBio())
                .status(Coach.STATUS_PENDING)
                .build();
        //createTime/updateTime/createUser/updateUser 由 @AutoFill 自动填充
        coachMapper.insert(coach);
        Long coachId = coach.getId();

        //资质证书批量保存
        List<CoachCertificate> certificates = coachRegisterDTO.getCertificates();
        if (certificates != null && !certificates.isEmpty()) {
            LocalDateTime now = LocalDateTime.now();
            for (CoachCertificate c : certificates) {
                c.setCoachId(coachId);
                c.setStatus(CoachCertificate.STATUS_PENDING);
                c.setCreateTime(now);
                c.setUpdateTime(now);
            }
            coachCertificateMapper.insertBatch(certificates);
        }
        return coachId;
    }

    /**
     * 教练登录
     */
    @Override
    public CoachLoginVO login(CoachLoginDTO coachLoginDTO) {
        String phone = coachLoginDTO.getPhone();
        String password = coachLoginDTO.getPassword();

        Coach coach = coachMapper.getByPhone(phone);
        if (coach == null) {
            throw new AccountNotFoundException(MessageConstant.ACCOUNT_NOT_FOUND);
        }

        //密码比对(BCrypt matches)
        if (!passwordEncoder.matches(password, coach.getPassword())) {
            throw new PasswordErrorException(MessageConstant.PASSWORD_ERROR);
        }

        //校验已审状态才能登录
        if (!Coach.STATUS_APPROVED.equals(coach.getStatus())) {
            throw new AccountLockedException("教练未通过审核,禁止登录");
        }

        //生成 jwt
        Map<String, Object> claims = new HashMap<>();
        claims.put(JwtClaimsConstant.COACH_ID, coach.getId());
        JwtUtil.JwtTokenResult tokenResult = JwtUtil.createJWT(
                jwtProperties.getCoachSecretKey(),
                jwtProperties.getCoachTtl(),
                claims);

        tokenBlacklistService.registerUserToken(
                String.valueOf(coach.getId()),
                tokenResult.getJti(),
                jwtProperties.getCoachTtl());

        return CoachLoginVO.builder()
                .id(coach.getId())
                .token(tokenResult.getToken())
                .name(coach.getName())
                .phone(coach.getPhone())
                .build();
    }

    /**
     * 审核教练(通过/驳回)
     */
    @Override
    @AuditLog(type = "coachAudit", detail = "审核教练")
    public void auditCoach(CoachAuditDTO coachAuditDTO) {
        Coach coach = Coach.builder()
                .id(coachAuditDTO.getCoachId())
                .status(coachAuditDTO.getStatus())
                .build();
        //updateUser/updateTime 由 @AutoFill 自动填充(管理端 BaseContext 为 empId)
        //注:coach 表无 reject_reason 列,驳回原因不持久化(证书审核才有)
        coachMapper.update(coach);
    }

    /**
     * 根据id查询教练(含资质证书)
     */
    @Override
    public CoachVO getById(Long id) {
        Coach coach = coachMapper.getById(id);
        if (coach == null) {
            throw new AccountNotFoundException(MessageConstant.ACCOUNT_NOT_FOUND);
        }
        coach.setPassword("****");
        coach.setIdNumber(AesEncryptUtil.decrypt(coach.getIdNumber(), aesKey));

        CoachVO coachVO = new CoachVO();
        BeanUtils.copyProperties(coach, coachVO);
        coachVO.setCertificates(coachCertificateMapper.getByCoachId(id));
        return coachVO;
    }

    /**
     * 管理端教练分页查询
     */
    @Override
    public PageResult pageQuery(CoachPageQueryDTO coachPageQueryDTO) {
        PageHelper.startPage(coachPageQueryDTO.getPage(), coachPageQueryDTO.getPageSize());
        Page<Coach> page = coachMapper.pageQuery(coachPageQueryDTO);
        List<Coach> records = page.getResult();
        if (records != null) {
            for (Coach c : records) {
                c.setPassword("****");
                c.setIdNumber(AesEncryptUtil.decrypt(c.getIdNumber(), aesKey));
            }
        }
        return new PageResult(page.getTotal(), records);
    }

    /**
     * 用户端按城市查询已审教练
     */
    @Override
    public PageResult listByCity(String cityCode, int page, int pageSize) {
        PageHelper.startPage(page, pageSize);
        Page<Coach> p = coachMapper.listByCity(cityCode);
        List<Coach> records = p.getResult();
        if (records != null) {
            for (Coach c : records) {
                c.setPassword("****");
                c.setIdNumber(null); // 用户端不返回身份证号
            }
        }
        return new PageResult(p.getTotal(), records);
    }

    /**
     * 审核教练资质证书
     */
    @Override
    public void auditCertificate(Long certId, Integer status, String rejectReason, Long auditUser) {
        CoachCertificate certificate = CoachCertificate.builder()
                .id(certId)
                .status(status)
                .rejectReason(rejectReason)
                .auditUser(auditUser)
                .auditTime(LocalDateTime.now())
                .updateTime(LocalDateTime.now())
                .build();
        coachCertificateMapper.updateStatus(certificate);
    }

    /**
     * 更新教练个人资料(仅可编辑字段)
     */
    @Override
    public void updateProfile(Coach coach) {
        Coach update = Coach.builder()
                .id(coach.getId())
                .name(coach.getName())
                .avatar(coach.getAvatar())
                .sex(coach.getSex())
                .bio(coach.getBio())
                .serviceRadiusKm(coach.getServiceRadiusKm())
                .cityCode(coach.getCityCode())
                .cityName(coach.getCityName())
                .idNumber(coach.getIdNumber())
                .updateTime(LocalDateTime.now())
                .build();
        coachMapper.update(update);
    }
}
