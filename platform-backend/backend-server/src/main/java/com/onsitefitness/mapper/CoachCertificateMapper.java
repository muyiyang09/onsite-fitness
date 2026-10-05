package com.onsitefitness.mapper;

import com.github.pagehelper.Page;
import com.onsitefitness.entity.CoachCertificate;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Select;

import java.util.List;

@Mapper
public interface CoachCertificateMapper {

    /**
     * 批量新增教练证书
     * @param certificates
     */
    void insertBatch(List<CoachCertificate> certificates);

    /**
     * 根据教练id查询证书列表
     * @param coachId
     * @return
     */
    @Select("select * from coach_certificate where coach_id = #{coachId} order by create_time desc")
    List<CoachCertificate> getByCoachId(Long coachId);

    /**
     * 分页查询证书(按状态)
     * @param status
     * @return
     */
    Page<CoachCertificate> listByPageQuery(Integer status);

    /**
     * 根据id查询证书
     * @param id
     * @return
     */
    @Select("select * from coach_certificate where id = #{id}")
    CoachCertificate getById(Long id);

    /**
     * 审核证书(更新状态/驳回原因/审核人/审核时间)
     * @param certificate
     */
    void updateStatus(CoachCertificate certificate);

}
