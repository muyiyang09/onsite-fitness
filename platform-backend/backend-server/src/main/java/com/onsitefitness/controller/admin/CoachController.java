package com.onsitefitness.controller.admin;

import com.onsitefitness.annotation.AdminOnly;
import com.onsitefitness.context.BaseContext;
import com.onsitefitness.dto.CoachAuditDTO;
import com.onsitefitness.dto.CoachPageQueryDTO;
import com.onsitefitness.result.PageResult;
import com.onsitefitness.result.Result;
import com.onsitefitness.service.CoachService;
import com.onsitefitness.vo.CoachVO;
import io.swagger.v3.oas.annotations.tags.Tag;
import io.swagger.v3.oas.annotations.Operation;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

/**
 * 管理端教练管理
 */
@RestController("adminCoachController")
@RequestMapping("/admin/coach")
@Tag(name = "管理端教练相关接口")
@Slf4j
public class CoachController {

    @Autowired
    private CoachService coachService;

    /**
     * 教练分页查询
     */
    @GetMapping("/page")
    @Operation(summary = "教练分页查询")
    public Result<PageResult> page(CoachPageQueryDTO coachPageQueryDTO) {
        log.info("教练分页查询：{}", coachPageQueryDTO);
        PageResult pageResult = coachService.pageQuery(coachPageQueryDTO);
        return Result.success(pageResult);
    }

    /**
     * 根据id查询教练(含资质证书)
     */
    @GetMapping("/{id}")
    @Operation(summary = "根据id查询教练")
    public Result<CoachVO> getById(@PathVariable Long id) {
        log.info("根据id查询教练：{}", id);
        CoachVO coachVO = coachService.getById(id);
        return Result.success(coachVO);
    }

    /**
     * 审核教练(通过/驳回)
     */
    @PostMapping("/audit")
    @Operation(summary = "审核教练")
    @AdminOnly
    public Result audit(@RequestBody CoachAuditDTO coachAuditDTO) {
        log.info("审核教练：{}", coachAuditDTO);
        coachAuditDTO.setAuditUser(BaseContext.getCurrentId());
        coachService.auditCoach(coachAuditDTO);
        return Result.success();
    }

    /**
     * 审核教练资质证书
     */
    @PostMapping("/cert/audit")
    @Operation(summary = "审核教练资质证书")
    @AdminOnly
    public Result auditCertificate(Long certId, Integer status, String rejectReason) {
        log.info("审核教练资质证书：certId={}, status={}, rejectReason={}", certId, status, rejectReason);
        coachService.auditCertificate(certId, status, rejectReason, BaseContext.getCurrentId());
        return Result.success();
    }
}
