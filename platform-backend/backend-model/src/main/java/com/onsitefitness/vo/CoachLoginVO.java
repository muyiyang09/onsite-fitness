package com.onsitefitness.vo;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.io.Serializable;

/**
 * 教练登录返回 VO
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class CoachLoginVO implements Serializable {

    private Long id;

    private String token;

    private String name;

    private String phone;

}
