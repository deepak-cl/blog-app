package com.springboot.blog.springbootblogrestapi.payload;

import lombok.AllArgsConstructor;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

@Setter
@Getter
@AllArgsConstructor
@NoArgsConstructor
public class JWTAuthResponse {
    private String accessToken;
    private String tokenType = "Bearer";

}
