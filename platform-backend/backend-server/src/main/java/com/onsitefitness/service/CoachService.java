package com.onsitefitness.service;

import com.onsitefitness.dto.CoachAuditDTO;
import com.onsitefitness.dto.CoachLoginDTO;
import com.onsitefitness.dto.CoachPageQueryDTO;
import com.onsitefitness.dto.CoachRegisterDTO;
import com.onsitefitness.entity.Coach;
import com.onsitefitness.result.PageResult;
import com.onsitefitness.vo.CoachLoginVO;
import com.onsitefitness.vo.CoachVO;

public interface CoachService {

    /**
     * 教练入驻(含资质证书)
     * @param coachRegisterDTO
     * @return coachId
     */
    Long register(CoachRegisterDTO coachRegisterDTO);

    /**
     * 教练登录(校验手机号+密码+已审状态,生成jwt)
     * @param coachLoginDTO
     * @return
     */
    CoachLoginVO login(CoachLoginDTO coachLoginDTO);

    /**
     * 审核教练(通过/驳回)
     * @param coachAuditDTO
     */
    void auditCoach(CoachAuditDTO coachAuditDTO);

    /**
     * 根据id查询教练(含资质证书)
     * @param id
     * @return
     */
    CoachVO getById(Long id);

    /**
     * 管理端教练分页查询
     * @param coachPageQueryDTO
     * @return
     */
    PageResult pageQuery(CoachPageQueryDTO coachPageQueryDTO);

    /**
     * 用户端按城市查询已审教练
     * @param cityCode
     * @param page
     * @param pageSize
     * @return
     */
    PageResult listByCity(String cityCode, int page, int pageSize);

    /**
     * 审核教练资质证书
     * @param certId
     * @param status
     * @param rejectReason
     * @param auditUser
     */
    void auditCertificate(Long certId, Integer status, String rejectReason, Long auditUser);

    /**
     * 更新教练个人资料(仅可编辑字段:姓名/头像/性别/简介/服务半径/城市/身份证)
     * @param coach
     */
    void updateProfile(Coach coach);

}
