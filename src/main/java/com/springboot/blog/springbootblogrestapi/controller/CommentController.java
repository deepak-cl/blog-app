package com.springboot.blog.springbootblogrestapi.controller;

import com.springboot.blog.springbootblogrestapi.payload.CommentDto;
import com.springboot.blog.springbootblogrestapi.service.CommentService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.responses.ApiResponse;
import io.swagger.v3.oas.annotations.security.SecurityRequirement;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/api")
@Tag(
        name = "CRUD REST APIs for Comment Resource"
)
public class CommentController {

    private CommentService commentService;

    public CommentController(CommentService commentService) {
        this.commentService = commentService;
    }

    @Operation(
            summary = "Create Comment REST API",
            description = "Create Comment REST API is used to save the comment in the database"
    )
    @ApiResponse(
            responseCode = "201",
            description = "Http Status 201 created"
    )
    @SecurityRequirement(
            name = "Bearer Authentication"
    )
    @PostMapping("/posts/{postId}/comments")
    public ResponseEntity<CommentDto> createComment(@PathVariable(value = "postId") long postId, @Valid @RequestBody CommentDto commentDto) {
        return new ResponseEntity<>(commentService.createComment(postId,commentDto), HttpStatus.CREATED);
    }

    @Operation(
            summary = "Get Comment By Post Id REST API",
            description = "Get Comment By Post Id REST API is used to get all the comments of particular post from the database"
    )
    @ApiResponse(
            responseCode = "200",
            description = "Http Status 200 success"
    )
    @GetMapping("/posts/{postId}/comments")
    public List<CommentDto> getCommentsByPostId(@PathVariable(value = "postId") long postId) {
        return commentService.getCommentsByPostId(postId);
    }

    @Operation(
            summary = "Get Comment By Comment Id and Post Id REST API",
            description = "Get comment by Post Id and Comment Id REST API is used to get a particular comment on the post from the database"
    )
    @ApiResponse(
            responseCode = "200",
            description = "Http Status 200 success"
    )
    @GetMapping("/posts/{postId}/comments/{id}")
    public ResponseEntity<CommentDto> getCommentById(@PathVariable(value = "postId") long postId,
                                                     @PathVariable(value = "id") long commentId) {
        CommentDto commentDto = commentService.getCommentById(postId, commentId);
        return new ResponseEntity<>(commentDto, HttpStatus.OK);
    }

    @Operation(
            summary = "Update Comment By Comment Id and Post Id REST API",
            description = "Update comment by Post Id and Comment Id REST API is used to update a particular comment on the post and save it in the database"
    )
    @ApiResponse(
            responseCode = "200",
            description = "Http Status 200 success"
    )
    @SecurityRequirement(
            name = "Bearer Authentication"
    )
    @PutMapping("/posts/{postId}/comments/{id}")
    public ResponseEntity<CommentDto> updateComment(@PathVariable(value = "postId") long postId,
                                                    @PathVariable(value = "id") long commentId,
                                                    @Valid @RequestBody CommentDto commentDto) {
        CommentDto updatedComment = commentService.updateComment(postId, commentId, commentDto);
        return new ResponseEntity<>(updatedComment, HttpStatus.OK);
    }

    @Operation(
            summary = "Delete Comment By Comment Id and Post Id REST API",
            description = "Delete comment by Post Id and Comment Id REST API is used to delete a particular comment on the post from the database"
    )
    @ApiResponse(
            responseCode = "200",
            description = "Http Status 200 success"
    )
    @SecurityRequirement(
            name = "Bearer Authentication"
    )
    @DeleteMapping("/posts/{postId}/comments/{id}")
    public ResponseEntity<String> deleteComment(@PathVariable(value = "postId") long postId,
                                                @PathVariable(value = "id") long commentId) {
        commentService.deleteComment(postId, commentId);
        return new ResponseEntity<>("Comment deleted successfully", HttpStatus.OK);
    }
}
